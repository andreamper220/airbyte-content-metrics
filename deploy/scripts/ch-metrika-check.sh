#!/bin/bash
set -eu
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT count(*) FROM analytics.raw_metrika_sessions"
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SHOW TABLES FROM analytics LIKE 'raw_metrika%'"
