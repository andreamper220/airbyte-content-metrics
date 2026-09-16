#!/usr/bin/env python3
"""Drop legacy Metrika table, migrate mart, trigger Airbyte sync."""
from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.error
import urllib.request

HOST = "content.netvolk.online"
BASE = "http://127.0.0.1:18091/api/v1"
CONN = "355e02e8-36a4-4ffc-99fe-4dd02beec41b"


def ch(sql: str) -> str:
    subprocess.check_call(
        [
            "docker",
            "exec",
            "content-metrics-clickhouse-1",
            "clickhouse-client",
            "--multiquery",
            "--query",
            sql,
        ]
    )
    return ""


def abctl_token() -> str:
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
        return json.loads(r.read())["access_token"]


def api_post(path: str, payload: dict, token: str) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Host": HOST, "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
        return json.loads(body) if body else {}


def main() -> int:
    print("==> ClickHouse: drop legacy raw_metrika_sessions")
    ch("DROP TABLE IF EXISTS analytics.raw_metrika_sessions;")
    print("==> ClickHouse: mart utm_campaign column")
    ch(
        "ALTER TABLE analytics.mart_web_traffic_daily "
        "ADD COLUMN IF NOT EXISTS utm_campaign LowCardinality(String) DEFAULT '';"
    )

    token = abctl_token()
    print("==> Trigger Airbyte sync")
    api_post("/connections/sync", {"connectionId": CONN}, token)

    for i in range(36):
        time.sleep(20)
        jobs = api_post("/jobs/list", {"configTypes": ["sync"], "configId": CONN, "limit": 1}, token)
        job = jobs.get("jobs", [{}])[0].get("job", {})
        status = job.get("status")
        print(f"    job {job.get('id')} status={status}")
        if status in ("succeeded", "failed", "cancelled"):
            if status != "succeeded":
                attempts = jobs.get("jobs", [{}])[0].get("attempts", [])
                if attempts:
                    print(attempts[0].get("failureSummary", {}))
                return 1
            break

    out = subprocess.check_output(
        [
            "docker",
            "exec",
            "content-metrics-clickhouse-1",
            "clickhouse-client",
            "-q",
            "SELECT count() FROM analytics.raw_metrika_sessions",
        ],
        text=True,
    ).strip()
    print(f"==> raw_metrika_sessions rows: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
