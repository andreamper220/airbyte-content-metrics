#!/bin/bash
set -eu
echo "==== REPO ===="
ls -d /var/www/content /var/www/content/content-analytics /opt/content 2>/dev/null || true
find /var/www /opt /root -maxdepth 3 -name 'docker-compose.yml' 2>/dev/null | head
echo "==== VIDEO API TRACE ===="
docker logs content-metrics-app-1 2>&1 | grep -E 'video/|DatabaseError|INVALID_JOIN' | tail -20
echo "==== DETAIL QUERY ===="
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT platform, video_id, title FROM analytics.mart_videos FINAL WHERE video_id = 'WPaMQAMjI7k'"
