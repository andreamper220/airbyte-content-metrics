#!/bin/bash
set -eu
CH="docker exec content-metrics-clickhouse-1 clickhouse-client -q"
echo "==== tables with comment ===="
$CH "SHOW TABLES FROM analytics" | grep -i comment || true
echo "==== raw_video_comments schema ===="
$CH "EXISTS TABLE analytics.raw_video_comments"
$CH "SHOW CREATE TABLE analytics.raw_video_comments" || true
echo "==== counts ===="
$CH "SELECT count() AS n, uniqExact(comment_id) AS ids, uniqExact((platform, video_id, text, author)) AS uniq_text FROM analytics.raw_video_comments"
$CH "SELECT count() AS n, uniqExact(comment_id) AS ids FROM analytics.raw_video_comments FINAL"
echo "==== empty comment_id ===="
$CH "SELECT countIf(comment_id = '') AS empty_id, countIf(comment_id != '') AS with_id FROM analytics.raw_video_comments FINAL"
echo "==== sample youtube ===="
$CH "SELECT video_id, comment_id, author, substring(text,1,80), likes FROM analytics.raw_video_comments FINAL WHERE platform='youtube' ORDER BY video_id, likes DESC LIMIT 30"
echo "==== dups by text ===="
$CH "SELECT platform, video_id, author, substring(text,1,60) AS t, count() AS n, groupArray(comment_id) FROM analytics.raw_video_comments FINAL GROUP BY platform, video_id, author, t HAVING n > 1 ORDER BY n DESC LIMIT 20"
echo "==== dups without FINAL ===="
$CH "SELECT platform, video_id, comment_id, count() AS n FROM analytics.raw_video_comments GROUP BY platform, video_id, comment_id HAVING n > 1 ORDER BY n DESC LIMIT 10"
echo "==== airbyte youtube comment tables ===="
$CH "SHOW TABLES FROM analytics"
