#!/bin/bash
set -eu
ROOT=""
for d in /var/www/content /opt/content /root/airbyte-content-metrics /root/content; do
  if [ -f "$d/deploy/docker-compose.yml" ] || [ -f "$d/content-analytics/app/main.py" ]; then
    ROOT="$d"
    break
  fi
done
echo "ROOT=$ROOT"
mkdir -p /tmp/popup-fix
# python files already uploaded to /tmp/popup-fix by scp
if [ -n "$ROOT" ] && [ -d "$ROOT/content-analytics/app" ]; then
  cp /tmp/popup-fix/queries.py "$ROOT/content-analytics/app/queries.py"
  cp /tmp/popup-fix/main.py "$ROOT/content-analytics/app/main.py"
  mkdir -p "$ROOT/content-analytics/frontend/src/pages"
  mkdir -p "$ROOT/content-analytics/frontend/src/components/dashboard"
  mkdir -p "$ROOT/content-analytics/frontend/src/lib"
  cp /tmp/popup-fix/dashboard.tsx "$ROOT/content-analytics/frontend/src/pages/dashboard.tsx"
  cp /tmp/popup-fix/video-dialog.tsx "$ROOT/content-analytics/frontend/src/components/dashboard/video-dialog.tsx"
  cp /tmp/popup-fix/api.ts "$ROOT/content-analytics/frontend/src/lib/api.ts"
fi
docker cp /tmp/popup-fix/queries.py content-metrics-app-1:/app/app/queries.py
docker cp /tmp/popup-fix/main.py content-metrics-app-1:/app/app/main.py
docker restart content-metrics-app-1
echo "waiting for health..."
for i in 1 2 3 4 5 6 7 8 9 10; do
  if docker exec content-metrics-app-1 python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')" >/dev/null 2>&1; then
    echo "healthy"
    break
  fi
  sleep 2
done
echo "==== test video endpoint via in-container python ===="
docker exec content-metrics-app-1 python - <<'PY'
from app.db import query
from app.queries import VIDEO_DETAIL, VIDEO_CLICKS, VIDEO_COMMENTS
vid = query("SELECT video_id, platform FROM analytics.mart_videos FINAL WHERE platform='youtube' ORDER BY published_at DESC LIMIT 1")
print("sample", vid)
if vid:
    p, i = vid[0]["platform"], vid[0]["video_id"]
    print("detail", query(VIDEO_DETAIL, {"platform": p, "video_id": i})[0].get("title"))
    print("clicks", query(VIDEO_CLICKS, {"platform": p, "video_id": i}))
    print("comments", len(query(VIDEO_COMMENTS, {"platform": p, "video_id": i})))
PY
