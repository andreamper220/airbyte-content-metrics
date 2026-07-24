REFRESH_MART_VIDEOS = """
INSERT INTO analytics.mart_videos
SELECT platform, video_id, title, published_at, url, views, likes, comments, shares, reach, snapshot_at
FROM analytics.v_refresh_mart_videos
"""

REFRESH_WEB_TRAFFIC = """
INSERT INTO analytics.mart_web_traffic_daily
SELECT
    toDate(parseDateTimeBestEffortOrNull(date)) AS date,
    'metrika' AS analytics_source,
    lower(UTMSource) AS utm_source,
    lower(UTMMedium) AS utm_medium,
    UTMContent AS utm_content,
    startURL AS landing_page,
    toUInt32(count()) AS sessions,
    toUInt32(uniqExact(clientID)) AS users,
    toUInt32(sum(toUInt32OrZero(pageViews))) AS pageviews
FROM analytics.raw_metrika_sessions
WHERE UTMSource != ''
GROUP BY date, utm_source, utm_medium, utm_content, landing_page
HAVING date IS NOT NULL
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
SELECT
    platform,
    video_id,
    title,
    published_at,
    views,
    likes,
    shares,
    round(engagement_rate, 4) AS engagement_rate,
    url,
    publish_day_sessions,
    publish_day_users
FROM analytics.v_viral_candidates
WHERE toDate(published_at) >= today() - {days:UInt32}
ORDER BY views DESC, publish_day_sessions DESC
"""

PLATFORM_CORRELATION = """
SELECT
    date,
    platform,
    total_views,
    top_video_id,
    top_video_title,
    top_video_views,
    web_sessions,
    web_users,
    round(sessions_per_view, 6) AS sessions_per_view
FROM analytics.v_platform_web_correlation
WHERE date >= today() - {days:UInt32}
ORDER BY date DESC, total_views DESC
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
    author,
    text,
    likes,
    published_at
FROM analytics.raw_video_comments FINAL
WHERE platform = {platform:String} AND video_id = {video_id:String}
ORDER BY likes DESC, published_at DESC
"""

PLATFORM_SUMMARY = """
SELECT
    platform,
    sum(total_views) AS views,
    sum(total_likes) AS likes,
    sum(video_count) AS videos
FROM analytics.mart_platform_daily
WHERE date >= today() - {days:UInt32}
GROUP BY platform
ORDER BY views DESC
"""

DAILY_TREND = """
SELECT
    p.date AS date,
    p.platform AS platform,
    p.total_views AS views,
    p.total_likes AS likes,
    coalesce(c.web_sessions, 0) AS web_sessions
FROM analytics.mart_platform_daily p
LEFT JOIN analytics.v_platform_web_correlation c
    ON p.date = c.date AND p.platform = c.platform
WHERE p.date >= today() - {days:UInt32}
ORDER BY p.date, p.platform
"""
