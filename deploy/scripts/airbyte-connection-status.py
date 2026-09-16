#!/usr/bin/env python3
import json
import re
import subprocess
import sys
import urllib.request

CONN = sys.argv[1] if len(sys.argv) > 1 else "355e02e8-36a4-4ffc-99fe-4dd02beec41b"
HOST = "content.netvolk.online"
BASE = "http://127.0.0.1:18091/api/v1"

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


def call(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Host": HOST, "Authorization": f"Bearer {tok}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


conn = call("/connections/get", {"connectionId": CONN})
print("name:", conn.get("name"))
print("status:", conn.get("status"))
print("lastSync:", conn.get("latestSyncJobCreatedAt") or conn.get("lastSync"))
print("job status:", conn.get("latestSyncJobStatus"))

jobs = call("/jobs/list", {"configTypes": ["sync"], "configId": CONN, "limit": 3})
print("jobs keys:", jobs.keys())
print(json.dumps(jobs, indent=2)[:3000])
