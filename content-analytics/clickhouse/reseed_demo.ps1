# Reload demo data with correct UTF-8 encoding (Windows PowerShell)
$ErrorActionPreference = "Stop"
$ch = "content-analytics-clickhouse-1"
$root = Split-Path -Parent $PSScriptRoot

docker cp "$root\clickhouse\seed_demo.sql" "${ch}:/tmp/seed_demo.sql"

$ensureComments = @"
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
"@

docker exec $ch clickhouse-client --multiquery --query $ensureComments

$truncate = @"
TRUNCATE TABLE analytics.raw_tiktok_videos;
TRUNCATE TABLE analytics.raw_youtube_videos;
TRUNCATE TABLE analytics.raw_instagram_media;
TRUNCATE TABLE analytics.raw_instagram_media_insights;
TRUNCATE TABLE analytics.raw_metrika_sessions;
TRUNCATE TABLE analytics.raw_video_comments;
TRUNCATE TABLE analytics.mart_videos;
TRUNCATE TABLE analytics.mart_web_traffic_daily;
TRUNCATE TABLE analytics.mart_platform_daily;
"@

docker exec $ch clickhouse-client --multiquery --query $truncate
docker exec $ch clickhouse-client --multiquery --queries-file /tmp/seed_demo.sql
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8080/api/refresh | Out-Null
Write-Host "Done. Open http://127.0.0.1:5173"
