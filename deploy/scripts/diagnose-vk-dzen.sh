#!/bin/bash
echo "=== Row counts ==="
docker exec content-metrics-clickhouse-1 clickhouse-client --query "SELECT count() FROM analytics.raw_vk_videos"
docker exec content-metrics-clickhouse-1 clickhouse-client --query "SELECT count() FROM analytics.raw_dzen_shorts"
docker exec content-metrics-clickhouse-1 clickhouse-client --query "SELECT platform, count() FROM analytics.mart_videos GROUP BY platform"

echo "=== Tables like raw_vk/raw_dzen ==="
docker exec content-metrics-clickhouse-1 clickhouse-client --query "SHOW TABLES FROM analytics LIKE 'raw_%'"

echo "=== Airbyte connections ==="
docker exec airbyte-abctl-control-plane kubectl exec -n airbyte-abctl airbyte-db-0 -- psql -U airbyte -d db-airbyte -t -c "SELECT name, id::text FROM connection ORDER BY name"

echo "=== VK connector read sample ==="
docker run --rm --user root -v /var/www/content/deploy/secrets/source-vk-config.json:/config.json:ro airbyte/source-vk:dev read --config /config.json --catalog /tmp/cat.json 2>&1 | head -5 || true
