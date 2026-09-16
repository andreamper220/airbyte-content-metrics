docker exec content-metrics-clickhouse-1 clickhouse-client -q "SHOW TABLES FROM analytics LIKE '%vk%'"
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT count() FROM analytics.raw_vk_videos"
