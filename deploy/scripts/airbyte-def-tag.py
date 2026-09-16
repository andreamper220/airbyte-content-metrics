#!/usr/bin/env python3
import json
import re
import subprocess
import urllib.request

HOST = "content.netvolk.online"
BASE = "http://127.0.0.1:18091/api/v1"
DEF = "7865dce4-2211-4f6a-88e5-9d0fe161afe7"

raw = subprocess.check_output(["abctl", "local", "credentials"], stderr=subprocess.STDOUT, text=True)
clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
cid = csec = ""
for line in clean.splitlines():
    if "Client-Id:" in line:
        cid = line.split("Client-Id:", 1)[1].strip()
    if "Client-Secret:" in line:
        csec = line.split("Client-Secret:", 1)[1].strip()

req = urllib.request.Request(
    f"{BASE}/applications/token",
    data=json.dumps({"client_id": cid, "client_secret": csec}).encode(),
    headers={"Content-Type": "application/json", "Host": HOST},
    method="POST",
)
with urllib.request.urlopen(req) as r:
    tok = json.loads(r.read())["access_token"]

req = urllib.request.Request(
    f"{BASE}/source_definitions/get",
    data=json.dumps({"sourceDefinitionId": DEF}).encode(),
    headers={"Content-Type": "application/json", "Host": HOST, "Authorization": f"Bearer {tok}"},
    method="POST",
)
with urllib.request.urlopen(req) as r:
    print(json.dumps(json.loads(r.read()), indent=2))
