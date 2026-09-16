CREATE TABLE IF NOT EXISTS analytics.raw_vk_videos
(
    video_id String,
    owner_id Int64,
    title String,
    description String,
    published_at Int64,
    duration UInt32,
    views UInt64,
    likes UInt64,
    comments UInt64,
    reposts UInt64,
    player_url String,
    share_url String,
    _airbyte_extracted_at DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree(_airbyte_extracted_at)
ORDER BY (video_id);

CREATE TABLE IF NOT EXISTS analytics.raw_dzen_shorts
(
    publication_id String,
    title String,
    published_at Int64,
    url String,
    views UInt64,
    likes UInt64,
    comments UInt64,
    content_type LowCardinality(String),
    _airbyte_extracted_at DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree(_airbyte_extracted_at)
ORDER BY (publication_id);

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

    UNION ALL

    SELECT
        'vk' AS platform,
        video_id,
        title,
        toDateTime(published_at) AS published_at,
        share_url AS url,
        views,
        likes,
        comments,
        reposts AS shares,
        0 AS reach,
        now() AS snapshot_at
    FROM analytics.raw_vk_videos FINAL

    UNION ALL

    SELECT
        'dzen' AS platform,
        publication_id AS video_id,
        title,
        toDateTime(published_at) AS published_at,
        url,
        views,
        likes,
        comments,
        0 AS shares,
        0 AS reach,
        now() AS snapshot_at
    FROM analytics.raw_dzen_shorts FINAL
);
