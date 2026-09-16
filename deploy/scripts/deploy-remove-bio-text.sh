#!/bin/bash
set -eu
sed -i 's/\r$//' /tmp/popup-fix/video-dialog.tsx
cp /tmp/popup-fix/video-dialog.tsx /var/www/content/content-analytics/frontend/src/components/dashboard/video-dialog.tsx
cd /var/www/content/deploy
docker compose build app
docker compose up -d app
