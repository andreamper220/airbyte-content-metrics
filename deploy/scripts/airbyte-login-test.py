#!/usr/bin/env python3
import json
import re
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

env_path = Path("/var/www/content/deploy/.env")
raw = subprocess.check_output(["abctl", "local", "credentials"], stderr=subprocess.STDOUT, text=True)
clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
fields = {}
for line in clean.splitlines():
    for key, label in [
        ("email", "Email:"),
        ("password", "Password:"),
        ("client_id", "Client-Id:"),
        ("client_secret", "Client-Secret:"),
    ]:
        if label in line:
            fields[key] = line.split(label, 1)[1].strip()

HOST = "content.netvolk.online"
BASE = "http://127.0.0.1:18091/api/v1"

print("fields", {k: (v[:4] + "..." if k == "password" else v) for k, v in fields.items()})

req = urllib.request.Request(
    f"{BASE}/users/login",
    data=json.dumps({"email": fields["email"], "password": fields["password"]}).encode(),
    headers={"Content-Type": "application/json", "Host": HOST},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode())
    print("login OK keys", list(body.keys()))
    print("accessToken present", bool(body.get("accessToken")))
except urllib.error.HTTPError as e:
    print("login FAIL", e.code, e.read().decode()[:300])

# update .env
text = env_path.read_text() if env_path.exists() else ""
for key, val in [
    ("AIRBYTE_USERNAME", fields.get("email", "")),
    ("AIRBYTE_PASSWORD", fields.get("password", "")),
    ("AIRBYTE_CLIENT_ID", fields.get("client_id", "")),
    ("AIRBYTE_CLIENT_SECRET", fields.get("client_secret", "")),
]:
    line = f"{key}={val}"
    if re.search(rf"^{key}=", text, re.M):
        text = re.sub(rf"^{key}=.*$", line, text, flags=re.M)
    else:
        text += line + "\n"
env_path.write_text(text)
print("updated", env_path)
