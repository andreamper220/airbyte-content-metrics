REFRESH_MART_VIDEOS = """
INSERT INTO analytics.mart_videos
SELECT platform, video_id, title, published_at, url, views, likes, comments, shares, reach, snapshot_at
FROM analytics.v_refresh_mart_videos
"""

REFRESH_WEB_TRAFFIC = """
INSERT INTO analytics.mart_web_traffic_daily
    (date, analytics_source, utm_source, utm_medium, utm_content, utm_campaign, landing_page, sessions, users, pageviews)
SELECT
    toDate(assumeNotNull(date)) AS date,
    'metrika' AS analytics_source,
    lower(UTMSource) AS utm_source,
    lower(ifNull(UTMMedium, '')) AS utm_medium,
    ifNull(UTMContent, '') AS utm_content,
    lower(ifNull(UTMCampaign, '')) AS utm_campaign,
    ifNull(startURL, '') AS landing_page,
    toUInt32(count()) AS sessions,
    toUInt32(uniqExact(clientID)) AS users,
    toUInt32(sum(toUInt32OrZero(pageViews))) AS pageviews
FROM analytics.raw_metrika_sessions
WHERE coalesce(UTMSource, '') != ''
GROUP BY
    date,
    lower(UTMSource),
    lower(ifNull(UTMMedium, '')),
    ifNull(UTMContent, ''),
    lower(ifNull(UTMCampaign, '')),
    ifNull(startURL, '')
"""

REFRESH_PLATFORM_DAILY = """
INSERT INTO analytics.mart_platform_daily
SELECT
    toDate(published_at) AS date,
    platform,
    sum(views) AS total_views,
    sum(likes) AS total_likes,
    sum(shares) AS total_shares,
    count() AS video_count,
    argMax(video_id, views) AS top_video_id,
    argMax(title, views) AS top_video_title,
    max(views) AS top_video_views
FROM analytics.mart_videos FINAL
GROUP BY date, platform
"""

TOP_VIRAL = """
WITH video_utm AS (
    SELECT
        v.platform AS platform,
        v.video_id AS video_id,
        coalesce(
            nullIf(extractURLParameter(coalesce(vk.description, ''), 'utm_content'), ''),
            concat('video_', leftPad(toString(
                row_number() OVER (PARTITION BY v.platform ORDER BY v.published_at, v.video_id)
            ), 3, '0'))
        ) AS utm_content
    FROM analytics.mart_videos AS v FINAL
    LEFT JOIN analytics.raw_vk_videos AS vk FINAL ON v.platform = 'vk' AND vk.video_id = v.video_id
    WHERE v.platform IN ('vk', 'dzen')
),
clicks_video AS (
    SELECT
        m.platform AS platform,
        r.UTMContent AS utm_content,
        toUInt32(uniqExact(r.clientID)) AS unique_clicks
    FROM analytics.raw_metrika_sessions AS r
    INNER JOIN analytics.v_platform_utm_map AS m ON lower(r.UTMSource) = m.utm_source
    WHERE m.platform IN ('vk', 'dzen')
      AND r.UTMContent LIKE 'video_%'
      AND lower(r.UTMMedium) IN ('clips', 'video')
      AND (coalesce(r.UTMCampaign, '') = '' OR lower(r.UTMCampaign) = 'organic')
    GROUP BY m.platform, r.UTMContent
),
clicks_week AS (
    SELECT
        m.platform AS platform,
        toMonday(toDate(assumeNotNull(r.date))) AS week_start,
        toUInt32(uniqExact(r.clientID)) AS unique_clicks
    FROM analytics.raw_metrika_sessions AS r
    INNER JOIN analytics.v_platform_utm_map AS m ON lower(r.UTMSource) = m.utm_source
    WHERE m.platform IN ('instagram', 'tiktok', 'youtube')
      AND r.UTMContent LIKE 'week_%'
      AND lower(r.UTMMedium) IN ('reels', 'shorts')
      AND (coalesce(r.UTMCampaign, '') = '' OR lower(r.UTMCampaign) = 'organic')
    GROUP BY m.platform, toMonday(toDate(assumeNotNull(r.date)))
)
SELECT
    v.platform AS platform,
    v.video_id AS video_id,
    v.title AS title,
    v.published_at AS published_at,
    v.views AS views,
    v.likes AS likes,
    v.shares AS shares,
    round(v.engagement_rate, 4) AS engagement_rate,
    v.url AS url,
    v.publish_day_sessions AS publish_day_sessions,
    v.publish_day_users AS publish_day_users,
    if(v.platform IN ('vk', 'dzen'), 'video', 'week') AS clicks_scope,
    coalesce(
        if(
            v.platform IN ('vk', 'dzen'),
            cv.unique_clicks,
            cw.unique_clicks
        ),
        0
    ) AS unique_clicks
FROM analytics.v_viral_candidates AS v
LEFT JOIN video_utm AS u ON v.platform = u.platform AND v.video_id = u.video_id
LEFT JOIN clicks_video AS cv
    ON v.platform IN ('vk', 'dzen') AND cv.platform = v.platform AND cv.utm_content = u.utm_content
LEFT JOIN clicks_week AS cw
    ON v.platform IN ('instagram', 'tiktok', 'youtube')
   AND cw.platform = v.platform
   AND cw.week_start = toMonday(toDate(v.published_at))
WHERE toDate(v.published_at) >= today() - {days:UInt32}
ORDER BY v.views DESC, unique_clicks DESC
"""

PLATFORM_CORRELATION = """
SELECT
    d.date AS date,
    d.platform AS platform,
    coalesce(p.total_views, 0) AS total_views,
    p.top_video_id AS top_video_id,
    p.top_video_title AS top_video_title,
    coalesce(p.top_video_views, 0) AS top_video_views,
    toMonday(d.date) AS week_start,
    addDays(toMonday(d.date), 6) AS week_end,
    if(d.platform IN ('instagram', 'tiktok', 'youtube'), 'week', 'day') AS clicks_scope,
    coalesce(
        if(
            d.platform IN ('instagram', 'tiktok', 'youtube'),
            w.unique_clicks,
            day_c.unique_clicks
        ),
        0
    ) AS unique_clicks
FROM (
    SELECT DISTINCT date, platform
    FROM analytics.mart_platform_daily FINAL
    WHERE date >= today() - {days:UInt32}
    UNION DISTINCT
    SELECT DISTINCT
        toDate(assumeNotNull(r.date)) AS date,
        m.platform AS platform
    FROM analytics.raw_metrika_sessions AS r
    INNER JOIN analytics.v_platform_utm_map AS m ON lower(r.UTMSource) = m.utm_source
    WHERE coalesce(r.UTMSource, '') != ''
      AND toDate(assumeNotNull(r.date)) >= today() - {days:UInt32}
) AS d
LEFT JOIN (
    SELECT
        date,
        platform,
        any(total_views) AS total_views,
        any(top_video_id) AS top_video_id,
        any(top_video_title) AS top_video_title,
        any(top_video_views) AS top_video_views
    FROM analytics.mart_platform_daily FINAL
    GROUP BY date, platform
) AS p
    ON p.date = d.date AND p.platform = d.platform
LEFT JOIN (
    SELECT
        m.platform AS platform,
        toMonday(toDate(assumeNotNull(r.date))) AS week_start,
        toUInt32(uniqExact(r.clientID)) AS unique_clicks
    FROM analytics.raw_metrika_sessions AS r
    INNER JOIN analytics.v_platform_utm_map AS m ON lower(r.UTMSource) = m.utm_source
    WHERE coalesce(r.UTMSource, '') != ''
    GROUP BY m.platform, week_start
) AS w
    ON d.platform IN ('instagram', 'tiktok', 'youtube')
   AND w.platform = d.platform
   AND w.week_start = toMonday(d.date)
LEFT JOIN (
    SELECT
        m.platform AS platform,
        toDate(assumeNotNull(r.date)) AS date,
        toUInt32(uniqExact(r.clientID)) AS unique_clicks
    FROM analytics.raw_metrika_sessions AS r
    INNER JOIN analytics.v_platform_utm_map AS m ON lower(r.UTMSource) = m.utm_source
    WHERE coalesce(r.UTMSource, '') != ''
    GROUP BY m.platform, date
) AS day_c
    ON d.platform IN ('vk', 'dzen')
   AND day_c.platform = d.platform
   AND day_c.date = d.date
ORDER BY toMonday(d.date) DESC, d.platform, d.date DESC
"""

VIDEO_DETAIL = """
SELECT
    platform,
    video_id,
    title,
    published_at,
    url,
    views,
    likes,
    comments AS comment_count,
    shares,
    reach
FROM analytics.mart_videos FINAL
WHERE platform = {platform:String} AND video_id = {video_id:String}
LIMIT 1
"""

VIDEO_COMMENTS = """
SELECT
    argMax(author, _airbyte_extracted_at) AS author,
    argMax(text, _airbyte_extracted_at) AS text,
    argMax(likes, _airbyte_extracted_at) AS likes,
    argMax(published_at, _airbyte_extracted_at) AS published_at
FROM analytics.raw_video_comments
WHERE platform = {platform:String}
  AND video_id = {video_id:String}
  AND coalesce(comment_id, '') != ''
GROUP BY comment_id
ORDER BY likes DESC, published_at DESC
"""

PLATFORM_SUMMARY = """
SELECT
    p.platform AS platform,
    sum(p.total_views) AS views,
    sum(p.total_likes) AS likes,
    sum(p.video_count) AS videos,
    coalesce(c.unique_clicks, 0) AS unique_clicks
FROM analytics.mart_platform_daily AS p FINAL
LEFT JOIN (
    SELECT
        m.platform AS platform,
        toUInt32(uniqExact(r.clientID)) AS unique_clicks
    FROM analytics.raw_metrika_sessions AS r
    INNER JOIN analytics.v_platform_utm_map AS m ON lower(r.UTMSource) = m.utm_source
    WHERE coalesce(r.UTMSource, '') != ''
      AND toDate(assumeNotNull(r.date)) >= today() - {days:UInt32}
    GROUP BY m.platform
) AS c ON p.platform = c.platform
WHERE p.date >= today() - {days:UInt32}
GROUP BY p.platform, c.unique_clicks
ORDER BY views DESC
"""

DAILY_TREND = """
SELECT
    p.date AS date,
    p.platform AS platform,
    p.total_views AS views,
    p.total_likes AS likes,
    coalesce(d.unique_clicks, 0) AS web_sessions
FROM analytics.mart_platform_daily AS p FINAL
LEFT JOIN (
    SELECT
        m.platform AS platform,
        toDate(assumeNotNull(r.date)) AS date,
        toUInt32(uniqExact(r.clientID)) AS unique_clicks
    FROM analytics.raw_metrika_sessions AS r
    INNER JOIN analytics.v_platform_utm_map AS m ON lower(r.UTMSource) = m.utm_source
    WHERE coalesce(r.UTMSource, '') != ''
    GROUP BY m.platform, date
) AS d ON p.date = d.date AND p.platform = d.platform
WHERE p.date >= today() - {days:UInt32}
ORDER BY p.date, p.platform
"""

METRIKA_STATUS = """
SELECT
    toUInt64((SELECT count() FROM analytics.raw_metrika_sessions)) AS raw_sessions,
    toUInt64((
        SELECT count()
        FROM analytics.raw_metrika_sessions
        WHERE coalesce(UTMSource, '') != ''
    )) AS utm_sessions,
    toUInt64((
        SELECT count()
        FROM analytics.raw_metrika_sessions
        WHERE coalesce(UTMSource, '') != ''
          AND toDate(assumeNotNull(date)) >= today() - {days:UInt32}
    )) AS utm_sessions_period,
    (SELECT max(_airbyte_extracted_at) FROM analytics.raw_metrika_sessions) AS last_extracted_at
"""

VIDEO_CLICKS = """
WITH video AS (
    SELECT platform, video_id, published_at, url
    FROM analytics.mart_videos FINAL
    WHERE platform = {platform:String} AND video_id = {video_id:String}
    LIMIT 1
),
utm_key AS (
    SELECT
        any(v.platform) AS platform,
        any(v.video_id) AS video_id,
        any(v.published_at) AS published_at,
        coalesce(
            if(
                any(v.platform) = 'vk',
                nullIf(extractURLParameter(coalesce(any(vk.description), ''), 'utm_content'), ''),
                CAST(NULL AS Nullable(String))
            ),
            concat('video_', any(v.video_id))
        ) AS video_utm
    FROM video AS v
    LEFT JOIN analytics.raw_vk_videos AS vk FINAL ON vk.video_id = v.video_id
)
SELECT
    if(any(v.platform) IN ('vk', 'dzen'), 'per_video', 'weekly_bio') AS mode,
    if(
        any(v.platform) IN ('vk', 'dzen'),
        any(u.video_utm),
        coalesce(anyIf(r.UTMContent, coalesce(r.UTMContent, '') != ''), '')
    ) AS utm_content,
    toMonday(toDate(any(v.published_at))) AS week_start,
    addDays(toMonday(toDate(any(v.published_at))), 6) AS week_end,
    toUInt32(uniqExactIf(r.clientID, coalesce(r.UTMSource, '') != '')) AS unique_clicks,
    toUInt32(countIf(coalesce(r.UTMSource, '') != '')) AS sessions
FROM video AS v
CROSS JOIN utm_key AS u
LEFT JOIN analytics.v_platform_utm_map AS m ON m.platform = v.platform
LEFT JOIN analytics.raw_metrika_sessions AS r ON lower(r.UTMSource) = m.utm_source
WHERE coalesce(r.UTMSource, '') = ''
   OR (
        v.platform IN ('instagram', 'tiktok', 'youtube')
        AND toMonday(toDate(assumeNotNull(r.date))) = toMonday(toDate(v.published_at))
   )
   OR (
        v.platform IN ('vk', 'dzen')
        AND (
            r.UTMContent = u.video_utm
            OR r.UTMContent = v.video_id
            OR r.UTMContent = concat('video_', v.video_id)
        )
   )
"""
