#!/bin/bash
set -eu
cd /var/www/content
tar -xzf /tmp/content-analytics-ui2.tgz
cd /var/www/content/deploy
docker compose build app
docker compose up -d app
docker exec content-metrics-clickhouse-1 clickhouse-client -q "ALTER TABLE analytics.mart_web_traffic_daily ADD COLUMN IF NOT EXISTS utm_campaign LowCardinality(String) DEFAULT ''"
docker exec content-metrics-clickhouse-1 clickhouse-client -q "TRUNCATE TABLE analytics.mart_web_traffic_daily"
docker exec content-metrics-clickhouse-1 clickhouse-client -q "INSERT INTO analytics.mart_web_traffic_daily (date, analytics_source, utm_source, utm_medium, utm_content, utm_campaign, landing_page, sessions, users, pageviews) SELECT toDate(assumeNotNull(date)), 'metrika', lower(UTMSource), lower(ifNull(UTMMedium, '')), ifNull(UTMContent, ''), lower(ifNull(UTMCampaign, '')), ifNull(startURL, ''), toUInt32(count()), toUInt32(uniqExact(clientID)), toUInt32(sum(toUInt32OrZero(pageViews))) FROM analytics.raw_metrika_sessions WHERE coalesce(UTMSource, '') != '' GROUP BY date, utm_source, utm_medium, utm_content, utm_campaign, landing_page"
echo "=== mart after ==="
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT date, utm_source, utm_medium, utm_content, sessions, users FROM analytics.mart_web_traffic_daily FINAL ORDER BY sessions DESC LIMIT 20"
echo "=== youtube utm dates ==="
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT date, UTMSource, UTMMedium, UTMContent, clientID FROM analytics.raw_metrika_sessions WHERE lower(ifNull(UTMSource,'')) IN ('youtube','tiktok','instagram') LIMIT 20"
