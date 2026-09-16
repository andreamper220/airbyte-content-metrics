#!/bin/bash
set -eu
sed -i 's/\r$//' /tmp/set-airbyte-schedule-15m.py
cp /tmp/set-airbyte-schedule-15m.py /var/www/content/deploy/scripts/set-airbyte-schedule-15m.py
python3 /tmp/set-airbyte-schedule-15m.py
cd /var/www/content/deploy
docker compose up -d app
sleep 5
docker exec content-metrics-app-1 python -c 'from app.config import settings; print("airbyte_min", settings.airbyte_sync_interval_minutes); print("enabled", settings.airbyte_sync_enabled); print("mart_min", settings.mart_refresh_interval_minutes)'
