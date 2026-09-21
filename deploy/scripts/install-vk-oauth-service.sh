#!/bin/bash
set -eu
cp /tmp/vk-oauth-login.py /var/www/content/deploy/scripts/vk-oauth-login.py
sed -i 's/\r$//' /var/www/content/deploy/scripts/vk-oauth-login.py
pkill -f 'vk-oauth-login.py' || true
sleep 1
systemctl stop vk-oauth.service 2>/dev/null || true
cat >/etc/systemd/system/vk-oauth.service <<'EOF'
[Unit]
Description=One-shot VK OAuth callback for content analytics
After=network.target

[Service]
Type=simple
WorkingDirectory=/var/www/content/deploy
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 -u /var/www/content/deploy/scripts/vk-oauth-login.py --serve
Restart=no

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl start vk-oauth.service
sleep 2
systemctl --no-pager --full status vk-oauth.service | head -20
journalctl -u vk-oauth.service -n 20 --no-pager
ss -lptn | grep 18473 || echo "port 18473 down"
