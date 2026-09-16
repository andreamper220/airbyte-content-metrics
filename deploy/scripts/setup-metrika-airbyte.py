#!/usr/bin/env python3
"""Point Metrika Airbyte source at patched dev image and re-sync."""
from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

HOST = "content.netvolk.online"
BASE = "http://127.0.0.1:18091/api/v1"
WS = "3f56ead9-e8a3-496d-a96d-98fd18e7d52c"
SOURCE_NAME = "Yandex Metrica (netvolk)"
CONN_NAME = f"{SOURCE_NAME} → ClickHouse"
CUSTOM_NAME = "Yandex Metrica (patched dev)"
REPO = "airbyte/source-yandex-metrica"
TAG = "dev"
CLUSTER = "airbyte-abctl"


def abctl() -> tuple[str, str]:
    raw = subprocess.check_output(["abctl", "local", "credentials"], stderr=subprocess.STDOUT, text=True)
    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    cid = csec = ""
    for line in clean.splitlines():
        if "Client-Id:" in line:
            cid = line.split("Client-Id:", 1)[1].strip()
        if "Client-Secret:" in line:
            csec = line.split("Client-Secret:", 1)[1].strip()
    return cid, csec


class Client:
    def __init__(self, cid: str, csec: str) -> None:
        req = urllib.request.Request(
            f"{BASE}/applications/token",
            data=json.dumps({"client_id": cid, "client_secret": csec}).encode(),
            headers={"Content-Type": "application/json", "Host": HOST},
            method="POST",
        )
        with urllib.request.urlopen(req) as r:
            self.tok = json.loads(r.read())["access_token"]

    def call(self, path: str, payload: dict) -> dict:
        req = urllib.request.Request(
            f"{BASE}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "Host": HOST, "Authorization": f"Bearer {self.tok}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                body = r.read()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{path} {exc.code}: {exc.read().decode()[:800]}") from exc


def load_image_into_kind() -> None:
    image = f"{REPO}:{TAG}"
    if subprocess.call(["bash", "-lc", "command -v kind >/dev/null"]) == 0:
        subprocess.check_call(["kind", "load", "docker-image", image, "-n", CLUSTER])
        return
    subprocess.check_call(
        f"docker save {image} | docker exec -i {CLUSTER}-control-plane ctr -n=k8s.io images import -",
        shell=True,
    )


def main() -> int:
    load_image_into_kind()
    config = json.loads(Path("/var/www/content/deploy/secrets/source-metrika-config.json").read_text())
    client = Client(*abctl())

    defs = client.call("/source_definitions/list_for_workspace", {"workspaceId": WS})["sourceDefinitions"]
    def_id = None
    for item in defs:
        if item.get("dockerRepository") == REPO and item.get("dockerImageTag") == TAG:
            def_id = item["sourceDefinitionId"]
            break
    if not def_id:
        created = client.call(
            "/source_definitions/create_custom",
            {
                "workspaceId": WS,
                "sourceDefinition": {
                    "name": CUSTOM_NAME,
                    "dockerRepository": REPO,
                    "dockerImageTag": TAG,
                    "documentationUrl": "https://docs.airbyte.com/integrations/sources/yandex-metrica",
                },
            },
        )
        def_id = created["sourceDefinitionId"]
        print("custom definition", def_id)
    else:
        print("using definition", def_id)

    dest_id = None
    for d in client.call("/destinations/list", {"workspaceId": WS})["destinations"]:
        if "clickhouse" in d.get("destinationName", "").lower():
            dest_id = d["destinationId"]
            break
    if not dest_id:
        raise SystemExit("ClickHouse destination missing")

    old_source_id = old_conn_id = None
    for s in client.call("/sources/list", {"workspaceId": WS})["sources"]:
        if s.get("name") == SOURCE_NAME:
            old_source_id = s["sourceId"]
    for c in client.call("/connections/list", {"workspaceId": WS})["connections"]:
        if c.get("name") == CONN_NAME or (old_source_id and c.get("sourceId") == old_source_id):
            old_conn_id = c["connectionId"]

    if old_conn_id:
        client.call("/connections/delete", {"connectionId": old_conn_id})
        print("deleted connection", old_conn_id)
    if old_source_id:
        client.call("/sources/delete", {"sourceId": old_source_id})
        print("deleted source", old_source_id)

    source = client.call(
        "/sources/create",
        {
            "name": SOURCE_NAME,
            "sourceDefinitionId": def_id,
            "workspaceId": WS,
            "connectionConfiguration": config,
        },
    )
    source_id = source["sourceId"]
    print("source", source_id)

    discover = client.call("/sources/discover_schema", {"sourceId": source_id})
    stream_cfg = None
    for st in discover.get("catalog", {}).get("streams", []):
        if st["stream"]["name"] == "sessions":
            st["config"] = {
                "syncMode": "incremental",
                "destinationSyncMode": "append",
                "cursorField": st["stream"].get("default_cursor_field") or [],
                "primaryKey": st["stream"].get("source_defined_primary_key") or [],
                "aliasName": "sessions",
                "selected": True,
            }
            stream_cfg = st
            break
    if not stream_cfg:
        raise SystemExit("sessions stream missing")

    conn = client.call(
        "/connections/create",
        {
            "name": CONN_NAME,
            "sourceId": source_id,
            "destinationId": dest_id,
            "workspaceId": WS,
            "namespaceDefinition": "customformat",
            "namespaceFormat": "analytics",
            "prefix": "raw_metrika_",
            "status": "active",
            "scheduleType": "basic",
            "scheduleData": {"basicSchedule": {"units": 6, "timeUnit": "hours"}},
            "syncCatalog": {"streams": [stream_cfg]},
        },
    )
    conn_id = conn["connectionId"]
    print("connection", conn_id)

    env_path = Path("/var/www/content/deploy/.env")
    text = env_path.read_text()
    ids = []
    m = re.search(r"^AIRBYTE_CONNECTION_IDS=(.*)$", text, re.M)
    if m and m.group(1).strip():
        ids = [x.strip() for x in m.group(1).split(",") if x.strip()]
    if old_conn_id and old_conn_id in ids:
        ids.remove(old_conn_id)
    if conn_id not in ids:
        ids.append(conn_id)
    line = "AIRBYTE_CONNECTION_IDS=" + ",".join(ids)
    text = re.sub(r"^AIRBYTE_CONNECTION_IDS=.*$", line, text, flags=re.M) if m else text + "\n" + line + "\n"
    env_path.write_text(text)

    client.call("/connections/sync", {"connectionId": conn_id})
    print("sync triggered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
