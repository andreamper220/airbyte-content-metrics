#!/bin/bash
set -euo pipefail
cd /var/www/content/deploy

echo "=== Connector check ==="
docker run --rm --user root \
  -v /var/www/content/deploy/secrets/source-vk-config.json:/config.json:ro \
  airbyte/source-vk:dev check --config /config.json 2>&1 | tail -3

echo "=== Discover streams ==="
docker run --rm --user root \
  -v /var/www/content/deploy/secrets/source-vk-config.json:/config.json:ro \
  airbyte/source-vk:dev discover --config /config.json 2>/dev/null | python3 -c "import sys,json; c=json.load(sys.stdin); print([s['stream']['name'] for s in c.get('catalog',{}).get('streams',[])])"

echo "=== Airbyte DB connections ==="
docker exec airbyte-abctl-control-plane kubectl exec -n airbyte-abctl airbyte-db-0 -- \
  psql -U airbyte -d db-airbyte -t -c "SELECT name, id::text FROM connection ORDER BY name;"

echo "=== Airbyte DB sources ==="
docker exec airbyte-abctl-control-plane kubectl exec -n airbyte-abctl airbyte-db-0 -- \
  psql -U airbyte -d db-airbyte -t -c "SELECT name, id::text FROM actor WHERE actor_type='source' ORDER BY name;"

echo "=== ClickHouse VK tables ==="
docker exec content-metrics-clickhouse-1 clickhouse-client --query \
  "SELECT name, total_rows FROM system.tables WHERE database='analytics' AND name LIKE '%vk%'"

echo "=== Sample read (first records) ==="
docker run --rm --user root \
  -v /var/www/content/deploy/secrets/source-vk-config.json:/config.json:ro \
  airbyte/source-vk:dev read --config /config.json --catalog /dev/stdin 2>/dev/null <<'CAT' | python3 -c "import sys,json; n=0
for line in sys.stdin:
  if not line.strip(): continue
  o=json.loads(line)
  if o.get('type')=='RECORD':
    n+=1
    if n<=3: print(o['record']['data'])
print('records', n)"
{"streams":[{"stream":{"name":"short_videos","json_schema":{},"supported_sync_modes":["full_refresh","incremental"],"source_defined_cursor":true,"default_cursor_field":["published_at"],"source_defined_primary_key":[["video_id"]]},"sync_mode":"full_refresh","destination_sync_mode":"overwrite","cursor_field":["published_at"]}]}
CAT
