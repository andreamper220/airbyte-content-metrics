#!/bin/bash
set -eu
docker exec content-metrics-clickhouse-1 clickhouse-client -q "
SELECT UTMSource, UTMMedium, UTMContent, count() AS c
FROM analytics.raw_metrika_sessions
GROUP BY UTMSource, UTMMedium, UTMContent
ORDER BY c DESC
LIMIT 20
"
