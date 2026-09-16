#!/usr/bin/env python3
import json, re, subprocess, urllib.request, urllib.error

HOST = "content.netvolk.online"
BASE = "http://127.0.0.1:18091/api/v1"
WS = "3f56ead9-e8a3-496d-a96d-98fd18e7d52c"

raw = subprocess.check_output(["abctl", "local", "credentials"], stderr=subprocess.STDOUT, text=True)
clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
cid = cs = ""
for line in clean.splitlines():
    if "Client-Id:" in line:
        cid = line.split("Client-Id:", 1)[1].strip()
    if "Client-Secret:" in line:
        cs = line.split("Client-Id:", 1)[1].strip() if False else line.split("Client-Secret:", 1)[1].strip()

req = urllib.request.Request(
    f"{BASE}/applications/token",
    data=json.dumps({"client_id": cid, "client_secret": cs}).encode(),
    headers={"Content-Type": "application/json", "Host": HOST},
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as resp:
    tok = json.loads(resp.read().decode())["access_token"]

def call(path, payload):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Host": HOST, "Authorization": f"Bearer {tok}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read()[:250]
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:250]

for path, payload in [
    ("/workspaces/list", {}),
    ("/workspaces/get", {"workspaceId": WS}),
    ("/destinations/list", {"workspaceId": WS}),
    ("/sources/list", {"workspaceId": WS}),
    ("/connections/list", {"workspaceId": WS}),
    ("/source_definitions/list_for_workspace", {"workspaceId": WS}),
]:
    code, body = call(path, payload)
    print(path, code, body)
