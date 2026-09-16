#!/bin/bash
set -eu
docker exec content-metrics-app-1 python -c 'import urllib.request
req = urllib.request.Request("http://127.0.0.1:8080/api/video/youtube/WPaMQAMjI7k")
try:
    with urllib.request.urlopen(req) as r:
        body = r.read()[:400]
        print("status", r.status, body)
except Exception as e:
    print("http_err", getattr(e, "code", None), e.read()[:400] if hasattr(e, "read") else e)
'
echo COMPOSE
ls -l /var/www/content/deploy/docker-compose.yml
