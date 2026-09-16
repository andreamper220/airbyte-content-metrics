#!/bin/bash
set -eu
echo "=== utm ==="
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT ifNull(UTMSource,'(empty)') s, ifNull(UTMMedium,'(empty)') m, ifNull(UTMContent,'(empty)') c, count() n FROM analytics.raw_metrika_sessions GROUP BY s,m,c ORDER BY n DESC LIMIT 20"
echo "=== mart ==="
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT date, utm_source, utm_medium, utm_content, sessions, users FROM analytics.mart_web_traffic_daily ORDER BY sessions DESC LIMIT 20"
echo "=== mapping ==="
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT * FROM analytics.v_platform_utm_map"
echo "=== corr sample ==="
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT date, platform, total_views, web_sessions FROM analytics.v_platform_web_correlation WHERE web_sessions > 0 ORDER BY date DESC LIMIT 20"
