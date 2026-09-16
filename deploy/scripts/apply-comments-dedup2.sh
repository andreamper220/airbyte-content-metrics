#!/bin/bash
set -eu
sed -i 's/\r$//' /tmp/migrate_youtube_comments.sql /tmp/queries.py
cp /tmp/migrate_youtube_comments.sql /var/www/content/content-analytics/clickhouse/migrate_youtube_comments.sql
cp /tmp/queries.py /var/www/content/content-analytics/app/queries.py
docker exec -i content-metrics-clickhouse-1 clickhouse-client --multiquery < /tmp/migrate_youtube_comments.sql
docker cp /tmp/queries.py content-metrics-app-1:/app/app/queries.py
docker restart content-metrics-app-1
sleep 6
echo "==== after view ===="
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT video_id, count() AS n FROM analytics.raw_video_comments GROUP BY video_id ORDER BY n DESC"
docker exec content-metrics-clickhouse-1 clickhouse-client -q "SELECT video_id, author, substring(text,1,50) FROM analytics.raw_video_comments ORDER BY video_id"
echo "==== health ===="
docker exec content-metrics-app-1 python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8080/health").read())'
