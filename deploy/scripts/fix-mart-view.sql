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
        'vk' AS platform,
        coalesce(video_id, '') AS video_id,
        coalesce(title, '') AS title,
        toDateTime(coalesce(published_at, 0)) AS published_at,
        coalesce(share_url, '') AS url,
        toUInt64(coalesce(views, 0)) AS views,
        toUInt64(coalesce(likes, 0)) AS likes,
        toUInt64(coalesce(comments, 0)) AS comments,
        toUInt64(coalesce(reposts, 0)) AS shares,
        0 AS reach,
        now() AS snapshot_at
    FROM analytics.raw_vk_short_videos

    UNION ALL

    SELECT
        'dzen' AS platform,
        coalesce(publication_id, '') AS video_id,
        coalesce(title, '') AS title,
        toDateTime(coalesce(published_at, 0)) AS published_at,
        coalesce(url, '') AS url,
        toUInt64(coalesce(views, 0)) AS views,
        toUInt64(coalesce(likes, 0)) AS likes,
        toUInt64(coalesce(comments, 0)) AS comments,
        0 AS shares,
        0 AS reach,
        now() AS snapshot_at
    FROM analytics.raw_dzen_shorts
);
