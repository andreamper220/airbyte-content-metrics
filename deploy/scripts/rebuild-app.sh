#!/bin/bash
set -eu
cd /var/www/content/deploy
# confirm frontend files landed
grep -n "setVideoOpen(true)" /var/www/content/content-analytics/frontend/src/pages/dashboard.tsx | head
docker compose build app
docker compose up -d app
docker compose ps app
