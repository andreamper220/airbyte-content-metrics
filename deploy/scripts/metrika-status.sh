#!/bin/bash
set -eu
echo "=== CH raw_metrika_sessions ==="
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT count() FROM analytics.raw_metrika_sessions"
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT count() FROM analytics.mart_web_traffic_daily"
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT min(date), max(date), groupUniqArray(10)(UTMSource) FROM analytics.raw_metrika_sessions" 2>/dev/null || true
