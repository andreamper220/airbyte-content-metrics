-- YouTube comments land in Airbyte table analytics.comments (MergeTree on _airbyte_raw_id).
-- Each sync appends the same threads again. Deduplicate by YouTube comment id.

CREATE OR REPLACE VIEW analytics.raw_video_comments AS
SELECT
    'youtube' AS platform,
    argMax(
        coalesce(nullIf(c.videoId, ''), JSONExtractString(c.topLevelComment, 'snippet', 'videoId')),
        c._airbyte_extracted_at
    ) AS video_id,
    JSONExtractString(c.topLevelComment, 'id') AS comment_id,
    argMax(JSONExtractString(c.topLevelComment, 'snippet', 'authorDisplayName'), c._airbyte_extracted_at) AS author,
    argMax(JSONExtractString(c.topLevelComment, 'snippet', 'textDisplay'), c._airbyte_extracted_at) AS text,
    argMax(toUInt32OrZero(JSONExtractString(c.topLevelComment, 'snippet', 'likeCount')), c._airbyte_extracted_at) AS likes,
    argMax(
        parseDateTimeBestEffortOrNull(JSONExtractString(c.topLevelComment, 'snippet', 'publishedAt')),
        c._airbyte_extracted_at
    ) AS published_at,
    max(c._airbyte_extracted_at) AS _airbyte_extracted_at
FROM analytics.comments AS c
WHERE length(c.topLevelComment) > 2
  AND JSONExtractString(c.topLevelComment, 'id') != ''
GROUP BY JSONExtractString(c.topLevelComment, 'id');
