#!/bin/bash
set -eu
docker exec content-metrics-clickhouse-1 clickhouse-client -q "DESCRIBE TABLE analytics.raw_metrika_sessions"
docker exec content-metrics-clickhouse-1 clickhouse-client -q "DESCRIBE TABLE analytics.video" | head -15
