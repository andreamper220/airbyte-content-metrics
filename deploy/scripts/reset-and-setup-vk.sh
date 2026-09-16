#!/bin/bash
# Reset Airbyte UI password and configure VK source + connection via API.
set -euo pipefail
ROOT=/var/www/content/deploy
cd "$ROOT"

NEW_PASS="$(openssl rand -base64 18 | tr -d '/+=' | head -c 24)"
EMAIL="${AIRBYTE_ADMIN_EMAIL:-anrewwolf68@gmail.com}"

echo "==> Reset Airbyte credentials"
abctl local credentials --email="$EMAIL" --password="$NEW_PASS" >/dev/null

# Persist for app + scripts (file mode 600 on server)
grep -q '^AIRBYTE_USERNAME=' .env 2>/dev/null && sed -i "s/^AIRBYTE_USERNAME=.*/AIRBYTE_USERNAME=$EMAIL/" .env || echo "AIRBYTE_USERNAME=$EMAIL" >> .env
grep -q '^AIRBYTE_PASSWORD=' .env 2>/dev/null && sed -i "s|^AIRBYTE_PASSWORD=.*|AIRBYTE_PASSWORD=$NEW_PASS|" .env || echo "AIRBYTE_PASSWORD=$NEW_PASS" >> .env

CID=$(abctl local credentials 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | awk -F': ' '/Client-Id:/ {print $2}')
CS=$(abctl local credentials 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | awk -F': ' '/Client-Secret:/ {print $2}')
grep -q '^AIRBYTE_CLIENT_ID=' .env 2>/dev/null && sed -i "s/^AIRBYTE_CLIENT_ID=.*/AIRBYTE_CLIENT_ID=$CID/" .env || echo "AIRBYTE_CLIENT_ID=$CID" >> .env
grep -q '^AIRBYTE_CLIENT_SECRET=' .env 2>/dev/null && sed -i "s|^AIRBYTE_CLIENT_SECRET=.*|AIRBYTE_CLIENT_SECRET=$CS|" .env || echo "AIRBYTE_CLIENT_SECRET=$CS" >> .env

echo "Airbyte login: $EMAIL / (saved in deploy/.env as AIRBYTE_PASSWORD)"

echo "==> Load VK connector image into kind"
docker save airbyte/source-vk:dev | docker exec -i airbyte-abctl-control-plane ctr -n=k8s.io images import - >/dev/null

echo "==> Configure VK in Airbyte"
python3 scripts/setup-vk-dzen.py --vk-only

echo "==> Done"
