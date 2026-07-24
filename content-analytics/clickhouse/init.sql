-- Content Analytics — ClickHouse schema
-- Airbyte writes to raw_* tables; marts are refreshed by the service or materialized views.

CREATE DATABASE IF NOT EXISTS analytics;

-- ---------------------------------------------------------------------------
-- Raw layer (Airbyte destination naming — adjust stream names to your catalog)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS analytics.raw_tiktok_videos
(
    item_id String,
    create_time Int64,
    caption String,
    share_url String,
    thumbnail_url String,
    video_duration Float64,
    video_views UInt64,
    likes UInt64,
    comments UInt64,
    shares UInt64,
    reach UInt64,
    average_time_watched Float64,
    total_time_watched Float64,
    full_video_watched_rate Float64,
    _airbyte_extracted_at DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree(_airbyte_extracted_at)
ORDER BY (item_id);

CREATE TABLE IF NOT EXISTS analytics.raw_youtube_videos
(
    id String,
    title String,
    published_at DateTime,
    view_count UInt64,
    like_count UInt64,
    comment_count UInt64,
    _airbyte_extracted_at DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree(_airbyte_extracted_at)
ORDER BY (id);

CREATE TABLE IF NOT EXISTS analytics.raw_instagram_media
(
    id String,
    caption String,
    timestamp DateTime,
    media_type LowCardinality(String),
    permalink String,
    _airbyte_extracted_at DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree(_airbyte_extracted_at)
ORDER BY (id);

CREATE TABLE IF NOT EXISTS analytics.raw_instagram_media_insights
(
    id String,
    reach UInt64,
    saved UInt64,
    shares UInt64,
    total_interactions UInt64,
    views UInt64,
    _airbyte_extracted_at DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree(_airbyte_extracted_at)
ORDER BY (id);

CREATE TABLE IF NOT EXISTS analytics.raw_ga4_sessions
(
    date Date,
    sessionSource String,
    sessionMedium String,
    sessionManualTerm String,
    landingPage String,
    sessions UInt32,
    totalUsers UInt32,
    screenPageViews UInt32,
    _airbyte_extracted_at DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree(_airbyte_extracted_at)
ORDER BY (date, sessionSource, sessionMedium, landingPage);

CREATE TABLE IF NOT EXISTS analytics.raw_metrika_sessions
(
    visitID String,
    date String,
    dateTime DateTime,
    startURL String,
    pageViews String,
    clientID String,
    UTMSource String,
    UTMMedium String,
    UTMContent String,
    UTMTerm String,
    bounce String,
    _airbyte_extracted_at DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree(_airbyte_extracted_at)
ORDER BY (visitID);

CREATE TABLE IF NOT EXISTS analytics.raw_video_comments
(
    platform LowCardinality(String),
    video_id String,
    comment_id String,
    author String,
    text String,
    likes UInt32,
    published_at DateTime,
    _airbyte_extracted_at DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree(_airbyte_extracted_at)
ORDER BY (platform, video_id, comment_id);

-- ---------------------------------------------------------------------------
-- Mart: unified video catalog (snapshot, latest metrics per video)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS analytics.mart_videos
(
    platform LowCardinality(String),
    video_id String,
    title String,
    published_at DateTime,
    url String,
    views UInt64,
    likes UInt64,
    comments UInt64,
    shares UInt64,
    reach UInt64,
    engagement_rate Float32 MATERIALIZED if(views > 0, (likes + comments + shares) / views, 0),
    snapshot_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(snapshot_at)
ORDER BY (platform, video_id);

-- ---------------------------------------------------------------------------
-- Mart: daily web traffic by UTM (no utm_campaign required)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS analytics.mart_web_traffic_daily
(
    date Date,
    analytics_source LowCardinality(String),
    utm_source LowCardinality(String),
    utm_medium LowCardinality(String),
    utm_content String,
    landing_page String,
    sessions UInt32,
    users UInt32,
    pageviews UInt32
)
ENGINE = ReplacingMergeTree()
ORDER BY (date, analytics_source, utm_source, utm_medium, landing_page);

-- ---------------------------------------------------------------------------
-- Mart: daily platform totals (for correlation without content_map)
-- Join key: platform ↔ utm_source mapping in views below
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS analytics.mart_platform_daily
(
    date Date,
    platform LowCardinality(String),
    total_views UInt64,
    total_likes UInt64,
    total_shares UInt64,
    video_count UInt32,
    top_video_id String,
    top_video_title String,
    top_video_views UInt64
)
ENGINE = ReplacingMergeTree()
ORDER BY (date, platform);

-- ---------------------------------------------------------------------------
-- Refresh marts from raw (run after each Airbyte sync)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW analytics.v_refresh_mart_videos AS
SELECT * FROM (
    SELECT
        'tiktok' AS platform,
        item_id AS video_id,
        caption AS title,
        toDateTime(create_time) AS published_at,
        share_url AS url,
        video_views AS views,
        likes,
        comments,
        shares,
        reach,
        now() AS snapshot_at
    FROM analytics.raw_tiktok_videos FINAL

    UNION ALL

    SELECT
        'youtube' AS platform,
        id AS video_id,
        title,
        published_at,
        concat('https://youtube.com/watch?v=', id) AS url,
        view_count AS views,
        like_count AS likes,
        comment_count AS comments,
        0 AS shares,
        0 AS reach,
        now() AS snapshot_at
    FROM analytics.raw_youtube_videos FINAL

    UNION ALL

    SELECT
        'instagram' AS platform,
        m.id AS video_id,
        m.caption AS title,
        m.timestamp AS published_at,
        m.permalink AS url,
        coalesce(i.views, 0) AS views,
        0 AS likes,
        0 AS comments,
        coalesce(i.shares, 0) AS shares,
        coalesce(i.reach, 0) AS reach,
        now() AS snapshot_at
    FROM analytics.raw_instagram_media m FINAL
    LEFT JOIN analytics.raw_instagram_media_insights i FINAL ON m.id = i.id
);

-- Platform → utm_source mapping (editable via /settings UI)
CREATE TABLE IF NOT EXISTS analytics.platform_utm_mapping
(
    platform LowCardinality(String),
    utm_source String,
    updated_at DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (platform, utm_source);

CREATE OR REPLACE VIEW analytics.v_platform_utm_map AS
SELECT platform, lower(utm_source) AS utm_source
FROM analytics.platform_utm_mapping FINAL;

-- Correlation: platform spike vs web traffic spike on same day
CREATE OR REPLACE VIEW analytics.v_platform_web_correlation AS
SELECT
    p.date AS date,
    p.platform AS platform,
    p.total_views AS total_views,
    p.top_video_id AS top_video_id,
    p.top_video_title AS top_video_title,
    p.top_video_views AS top_video_views,
    coalesce(sum(w.sessions), 0) AS web_sessions,
    coalesce(sum(w.users), 0) AS web_users,
    groupArrayDistinct(w.utm_medium) AS utm_mediums,
    if(p.total_views > 0, coalesce(sum(w.sessions), 0) / p.total_views, 0) AS sessions_per_view
FROM analytics.mart_platform_daily p
LEFT JOIN analytics.v_platform_utm_map m ON p.platform = m.platform
LEFT JOIN analytics.mart_web_traffic_daily w
    ON w.date = p.date AND lower(w.utm_source) = m.utm_source
GROUP BY
    p.date, p.platform, p.total_views,
    p.top_video_id, p.top_video_title, p.top_video_views;

-- Top "viral" videos: high views + web traffic on publish day
CREATE OR REPLACE VIEW analytics.v_viral_candidates AS
SELECT
    v.platform AS platform,
    v.video_id AS video_id,
    v.title AS title,
    v.published_at AS published_at,
    v.views AS views,
    v.likes AS likes,
    v.shares AS shares,
    v.engagement_rate AS engagement_rate,
    v.url AS url,
    coalesce(w.sessions, 0) AS publish_day_sessions,
    coalesce(w.users, 0) AS publish_day_users
FROM analytics.mart_videos v FINAL
LEFT JOIN (
    SELECT
        m.platform AS platform,
        w.date AS date,
        sum(w.sessions) AS sessions,
        sum(w.users) AS users
    FROM analytics.v_platform_utm_map m
    INNER JOIN (
        SELECT date, utm_source, sum(sessions) AS sessions, sum(users) AS users
        FROM analytics.mart_web_traffic_daily
        GROUP BY date, utm_source
    ) w ON lower(w.utm_source) = m.utm_source
    GROUP BY m.platform, w.date
) w ON toDate(v.published_at) = w.date AND v.platform = w.platform
WHERE v.views >= 1000;
