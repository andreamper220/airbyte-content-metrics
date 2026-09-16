#!/bin/bash
set -eu
echo "==== APP ENV ===="
grep -E 'AIRBYTE_SYNC|MART_REFRESH' /var/www/content/deploy/.env || true
echo "==== CONTAINER ENV ===="
docker exec content-metrics-app-1 python -c 'from app.config import settings; print("enabled", settings.airbyte_sync_enabled); print("airbyte_min", settings.airbyte_sync_interval_minutes); print("mart_min", settings.mart_refresh_interval_minutes); print("ids", settings.airbyte_connection_ids); print("api", settings.airbyte_api_url)'
