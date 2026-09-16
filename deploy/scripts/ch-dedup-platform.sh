#!/bin/bash
set -eu
docker exec content-metrics-clickhouse-1 clickhouse-client -q "OPTIMIZE TABLE analytics.mart_platform_daily FINAL"
docker exec content-metrics-clickhouse-1 clickhouse-client -q "TRUNCATE TABLE analytics.mart_platform_daily"
docker exec content-metrics-clickhouse-1 clickhouse-client -q "INSERT INTO analytics.mart_platform_daily SELECT toDate(published_at) AS date, platform, sum(views), sum(likes), sum(shares), count(), argMax(video_id, views), argMax(title, views), max(views) FROM analytics.mart_videos FINAL GROUP BY date, platform"
echo "=== platform daily counts ==="
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT date, platform, count() FROM analytics.mart_platform_daily GROUP BY date, platform HAVING count() > 1"
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT date, platform, total_views FROM analytics.mart_platform_daily FINAL WHERE platform='youtube' AND date >= '2026-09-14' ORDER BY date"
