#!/bin/bash
set -eu
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT name FROM system.columns WHERE database='analytics' AND table='raw_metrika_sessions' AND name LIKE '%UTM%'"
docker logs content-metrics-app-1 --tail 40
