#!/bin/sh
# Reload demo data with UTF-8 (run inside repo: sh clickhouse/reseed_demo.sh)
set -e
CH=content-analytics-clickhouse-1

docker cp clickhouse/seed_demo.sql "$CH:/tmp/seed_demo.sql"

docker exec "$CH" clickhouse-client --multiquery --query "
TRUNCATE TABLE analytics.raw_tiktok_videos;
TRUNCATE TABLE analytics.raw_youtube_videos;
TRUNCATE TABLE analytics.raw_instagram_media;
TRUNCATE TABLE analytics.raw_instagram_media_insights;
TRUNCATE TABLE analytics.raw_metrika_sessions;
TRUNCATE TABLE analytics.raw_video_comments;
TRUNCATE TABLE analytics.mart_videos;
TRUNCATE TABLE analytics.mart_web_traffic_daily;
TRUNCATE TABLE analytics.mart_platform_daily;
"

docker exec "$CH" clickhouse-client --multiquery --queries-file /tmp/seed_demo.sql
curl -s -X POST http://localhost:8081/api/refresh
echo ""
echo "Done. Open http://localhost:8081"
