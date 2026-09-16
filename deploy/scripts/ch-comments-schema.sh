#!/bin/bash
set -eu
CH="docker exec content-metrics-clickhouse-1 clickhouse-client -q"
echo "==== comments create ===="
$CH "SHOW CREATE TABLE analytics.comments"
echo "==== comments sample keys ===="
$CH "SELECT name, type FROM system.columns WHERE database='analytics' AND table='comments'"
echo "==== comments dups ===="
$CH "SELECT count() AS n, uniqExact(_airbyte_raw_id) AS raw_ids FROM analytics.comments"
$CH "SELECT JSONExtractString(topLevelComment, 'id') AS cid, count() FROM analytics.comments GROUP BY cid ORDER BY count() DESC LIMIT 10"
