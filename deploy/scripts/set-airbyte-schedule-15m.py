#!/usr/bin/env python3
"""Set all Airbyte connections to a 15-minute basic schedule."""
from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

HOST = "content.netvolk.online"
BASE = "http://127.0.0.1:18091/api/v1"
DEFAULT_WS = "3f56ead9-e8a3-496d-a96d-98fd18e7d52c"
SCHEDULE = {"basicSchedule": {"units": 15, "timeUnit": "minutes"}}
UPDATE_KEYS = (
    "connectionId",
    "name",
    "namespaceDefinition",
    "namespaceFormat",
    "prefix",
    "sourceId",
    "destinationId",
    "operationIds",
    "syncCatalog",
    "scheduleType",
    "scheduleData",
    "status",
    "resourceRequirements",
    "sourceCatalogId",
    "geography",
    "notifySchemaChanges",
    "nonBreakingChangesPreference",
    "configurations",
)


def creds() -> tuple[str, str, str, str]:
    raw = subprocess.check_output(["abctl", "local", "credentials"], stderr=subprocess.STDOUT, text=True)
    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    email = password = cid = csec = ""
    for line in clean.splitlines():
        if "Email:" in line:
            email = line.split("Email:", 1)[1].strip()
        if "Password:" in line:
            password = line.split("Password:", 1)[1].strip()
        if "Client-Id:" in line:
            cid = line.split("Client-Id:", 1)[1].strip()
        if "Client-Secret:" in line:
            csec = line.split("Client-Secret:", 1)[1].strip()
    return email, password, cid, csec


def call(token: str, path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Host": HOST,
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"{path} failed ({exc.code}): {detail[:500]}") from exc


def workspace_id() -> str:
    env_path = Path("/var/www/content/deploy/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("AIRBYTE_WORKSPACE_ID="):
                value = line.split("=", 1)[1].strip()
                if value:
                    return value
    return DEFAULT_WS


def auth_token() -> str:
    email, password, cid, csec = creds()
    if email and password:
        req = urllib.request.Request(
            f"{BASE}/users/login",
            data=json.dumps({"email": email, "password": password}).encode(),
            headers={"Content-Type": "application/json", "Host": HOST},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                login = json.loads(resp.read().decode())
            token = login.get("accessToken") or login.get("token") or ""
            if token:
                return token
        except urllib.error.HTTPError:
            pass
    req = urllib.request.Request(
        f"{BASE}/applications/token",
        data=json.dumps({"client_id": cid, "client_secret": csec}).encode(),
        headers={"Content-Type": "application/json", "Host": HOST},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())["access_token"]


def main() -> int:
    token = auth_token()
    ws = workspace_id()
    connections = call(token, "/connections/list", {"workspaceId": ws}).get("connections", [])
    print(f"workspace {ws}: {len(connections)} connections")
    for conn in connections:
        conn_id = conn["connectionId"]
        full = call(token, "/connections/get", {"connectionId": conn_id})
        old = full.get("scheduleData") or full.get("schedule")
        payload = {key: full[key] for key in UPDATE_KEYS if key in full}
        payload["scheduleType"] = "basic"
        payload["scheduleData"] = SCHEDULE
        payload["status"] = full.get("status") or "active"
        updated = call(token, "/connections/update", payload)
        print(
            f"{updated.get('name') or full.get('name')} "
            f"{conn_id} {old} -> {updated.get('scheduleData')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
