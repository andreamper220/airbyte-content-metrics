#!/bin/bash
set -euo pipefail
CFG=/etc/nginx/sites-available/content
python3 <<'PY'
from pathlib import Path
p = Path("/etc/nginx/sites-available/content")
text = p.read_text()
good = """    location = /vk-oauth-callback {
        proxy_pass http://127.0.0.1:18473/vk-oauth-callback;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

"""
import re
text = re.sub(
    r"    location = /vk-oauth-callback \{.*?\n    \}\n\n",
    good,
    text,
    count=1,
    flags=re.S,
)
if "vk-oauth-callback" not in text:
    text = text.replace(
        "    location / {\n        proxy_pass http://127.0.0.1:8090;",
        good + "    location / {\n        proxy_pass http://127.0.0.1:8090;",
        1,
    )
p.write_text(text)
print("fixed")
PY
nginx -t
systemctl reload nginx
