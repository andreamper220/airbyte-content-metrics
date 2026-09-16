#!/bin/bash
set -eu
sleep 3
docker exec content-metrics-app-1 python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8080/health").read())'
docker logs content-metrics-app-1 --tail 15 2>&1 | tail -15
