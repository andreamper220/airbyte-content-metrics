#!/bin/bash
set -eu
ENV=/var/www/content/deploy/.env
if grep -q '^AIRBYTE_SYNC_INTERVAL_MINUTES=' "$ENV"; then
  sed -i 's/^AIRBYTE_SYNC_INTERVAL_MINUTES=.*/AIRBYTE_SYNC_INTERVAL_MINUTES=15/' "$ENV"
else
  printf '\nAIRBYTE_SYNC_INTERVAL_MINUTES=15\n' >> "$ENV"
fi
grep '^AIRBYTE_SYNC' "$ENV" || true
cp /tmp/set-airbyte-schedule-15m.py /var/www/content/deploy/scripts/set-airbyte-schedule-15m.py
cp /tmp/docker-compose.yml /var/www/content/deploy/docker-compose.yml
python3 /tmp/set-airbyte-schedule-15m.py
cd /var/www/content/deploy
docker compose up -d app
echo "==== CONTAINER ===="
sleep 4
docker exec content-metrics-app-1 python -c 'from app.config import settings; print(settings.airbyte_sync_interval_minutes, settings.airbyte_sync_enabled)'
