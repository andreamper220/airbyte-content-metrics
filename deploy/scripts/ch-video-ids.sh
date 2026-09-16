#!/bin/bash
set -eu
docker logs content-metrics-app-1 --tail 80
echo "=== sample ids ==="
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT date, platform, top_video_id, top_video_title FROM analytics.mart_platform_daily FINAL WHERE date >= '2026-09-14' ORDER BY date"
