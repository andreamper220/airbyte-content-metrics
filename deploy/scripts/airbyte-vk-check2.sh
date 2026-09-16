#!/bin/bash
docker exec airbyte-abctl-control-plane kubectl exec -n airbyte-abctl airbyte-db-0 -- \
  psql -U airbyte -d db-airbyte -t -c "SELECT name, id::text FROM connection ORDER BY name;"
docker exec airbyte-abctl-control-plane kubectl exec -n airbyte-abctl airbyte-db-0 -- \
  psql -U airbyte -d db-airbyte -t -c "SELECT name, id::text FROM actor WHERE actor_type='source' ORDER BY name;"
docker exec content-metrics-clickhouse-1 clickhouse-client --query \
  "SELECT name, total_rows FROM system.tables WHERE database='analytics' AND name LIKE '%vk%'"
docker run --rm --user root -v /var/www/content/deploy/secrets/source-vk-config.json:/config.json:ro \
  airbyte/source-vk:dev read --config /config.json --catalog /tmp/cat.json 2>/dev/null | head -1 || true
