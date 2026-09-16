#!/bin/bash
set -eu
docker exec content-metrics-clickhouse-1 clickhouse-client -q "DESCRIBE TABLE analytics.raw_metrika_sessions" | head -25
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT count(), countIf(UTMSource!='') FROM analytics.raw_metrika_sessions"
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT count() FROM analytics.mart_web_traffic_daily"
