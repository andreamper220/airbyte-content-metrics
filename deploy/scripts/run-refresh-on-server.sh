#!/bin/bash
set -euo pipefail
docker exec content-metrics-app-1 sh -c 'cd /app && python3 -c "from app.refresh_service import run_refresh_cycle; print(run_refresh_cycle())"'
docker exec content-metrics-clickhouse-1 clickhouse-client --query "SELECT platform, count() FROM analytics.mart_videos GROUP BY platform ORDER BY platform"
