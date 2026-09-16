#!/bin/bash
set -eu
echo "==== APP LOGS ===="
docker logs content-metrics-app-1 --tail 80 2>&1 || docker logs content-metrics-app --tail 80 2>&1 || true
echo "==== CONTAINERS ===="
docker ps --format '{{.Names}}' | grep -E 'content|app|click' || true
echo "==== VIDEO IDS ===="
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT date, platform, top_video_id, length(top_video_id) FROM analytics.mart_platform_daily FINAL WHERE date >= '2026-09-10' ORDER BY date, platform LIMIT 30"
echo "==== TEST VIDEO_CLICKS ===="
VID=$(docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT top_video_id FROM analytics.mart_platform_daily FINAL WHERE platform='youtube' AND top_video_id != '' ORDER BY date DESC LIMIT 1")
echo "sample youtube id: $VID"
docker exec content-metrics-clickhouse-1 clickhouse-client --param_platform=youtube --param_video_id="$VID" -q "
WITH video AS (
    SELECT platform, video_id, published_at, url
    FROM analytics.mart_videos FINAL
    WHERE platform = {platform:String} AND video_id = {video_id:String}
)
SELECT count() FROM video
" || true
echo "==== CURL VIDEO API ===="
docker exec content-metrics-app-1 python - <<'PY'
import urllib.request, json
try:
    import os
    # get a video id from CH via app? just hit health and list frontend assets
    print('health', urllib.request.urlopen('http://127.0.0.1:8080/health').read())
except Exception as e:
    print('err', e)
PY
echo "==== FRONTEND BUNDLE ===="
docker exec content-metrics-app-1 sh -c 'ls /app/frontend/dist/assets; grep -o "api/video" /app/frontend/dist/assets/*.js | head; grep -c cursor-pointer /app/frontend/dist/assets/*.js || true'
