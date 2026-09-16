#!/usr/bin/env python3
"""Configure VK + Dzen Airbyte sources and ClickHouse connections."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def abctl_credentials() -> tuple[str, str, str, str]:
    raw = subprocess.check_output(["abctl", "local", "credentials"], stderr=subprocess.STDOUT, text=True)
    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    email = password = client_id = client_secret = ""
    for line in clean.splitlines():
        if "Email:" in line:
            email = line.split("Email:", 1)[1].strip()
        if "Password:" in line:
            password = line.split("Password:", 1)[1].strip()
        if "Client-Id:" in line:
            client_id = line.split("Client-Id:", 1)[1].strip()
        if "Client-Secret:" in line:
            client_secret = line.split("Client-Secret:", 1)[1].strip()
    return email, password, client_id, client_secret


class AirbyteClient:
    def __init__(
        self,
        host: str,
        client_id: str,
        client_secret: str,
        workspace_id: str = "",
        email: str = "",
        password: str = "",
    ) -> None:
        self.host = host
        self.base = "http://127.0.0.1:18091/api/v1"
        self.workspace_id = workspace_id
        self.token = ""
        if email and password:
            login_req = urllib.request.Request(
                f"{self.base}/users/login",
                data=json.dumps({"email": email, "password": password}).encode(),
                headers={"Content-Type": "application/json", "Host": host},
                method="POST",
            )
            try:
                with urllib.request.urlopen(login_req, timeout=30) as resp:
                    login = json.loads(resp.read().decode())
                self.token = login.get("accessToken") or login.get("token") or ""
            except urllib.error.HTTPError:
                pass
        if not self.token:
            token_req = urllib.request.Request(
                f"{self.base}/applications/token",
                data=json.dumps({"client_id": client_id, "client_secret": client_secret}).encode(),
                headers={"Content-Type": "application/json", "Host": host},
                method="POST",
            )
            with urllib.request.urlopen(token_req, timeout=30) as resp:
                self.token = json.loads(resp.read().decode())["access_token"]

    def workspace_id_or_fetch(self) -> str:
        if self.workspace_id:
            self.call("/workspaces/get", {"workspaceId": self.workspace_id})
            return self.workspace_id
        result = self.call("/workspaces/list", {})
        self.workspace_id = result["workspaces"][0]["workspaceId"]
        return self.workspace_id

    def call(self, path: str, payload: dict | None = None) -> dict:
        body = json.dumps(payload or {}).encode()
        req = urllib.request.Request(
            f"{self.base}{path}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Host": self.host,
                "Authorization": f"Bearer {self.token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"{path} failed ({exc.code}): {detail}") from exc


def register_connector(client: AirbyteClient, workspace_id: str, image: str, name: str) -> str:
    result = client.call(
        "/source_definitions/create_custom",
        {
            "workspaceId": workspace_id,
            "sourceDefinition": {
                "name": name,
                "dockerRepository": image,
                "dockerImageTag": "dev",
                "documentationUrl": "https://example.com",
            },
        },
    )
    return result["sourceDefinitionId"]


def find_destination(client: AirbyteClient, workspace_id: str) -> str:
    result = client.call("/destinations/list", {"workspaceId": workspace_id})
    for dest in result.get("destinations", []):
        if "clickhouse" in dest.get("destinationName", "").lower():
            return dest["destinationId"]
    if result.get("destinations"):
        return result["destinations"][0]["destinationId"]
    raise RuntimeError("ClickHouse destination not found in Airbyte")


def ensure_source(
    client: AirbyteClient,
    workspace_id: str,
    name: str,
    definition_id: str,
    config: dict,
) -> str:
    sources = client.call("/sources/list", {"workspaceId": workspace_id}).get("sources", [])
    for source in sources:
        if source.get("name") == name:
            print(f"Source exists: {name} ({source['sourceId']})")
            return source["sourceId"]
    created = client.call(
        "/sources/create",
        {
            "name": name,
            "sourceDefinitionId": definition_id,
            "workspaceId": workspace_id,
            "connectionConfiguration": config,
        },
    )
    print(f"Created source: {name} ({created['sourceId']})")
    return created["sourceId"]


def build_sync_catalog(discover: dict, stream_name: str, alias_name: str | None = None) -> dict:
    alias = alias_name or stream_name
    for stream in discover.get("catalog", {}).get("streams", []):
        if stream["stream"]["name"] != stream_name:
            continue
        stream["config"] = {
            "syncMode": "incremental",
            "destinationSyncMode": "append",
            "cursorField": stream["stream"].get("default_cursor_field") or [],
            "primaryKey": stream["stream"].get("source_defined_primary_key") or [],
            "aliasName": alias,
            "selected": True,
        }
        return {"streams": [stream]}
    raise RuntimeError(f"Stream not found in discover: {stream_name}")


def ensure_connection(
    client: AirbyteClient,
    workspace_id: str,
    name: str,
    source_id: str,
    destination_id: str,
    stream_name: str,
    table_prefix: str,
    stream_alias: str | None = None,
) -> str:
    connections = client.call("/connections/list", {"workspaceId": workspace_id}).get("connections", [])
    for conn in connections:
        if conn.get("sourceId") == source_id:
            print(f"Connection exists: {conn['connectionId']}")
            return conn["connectionId"]

    discover = client.call("/sources/discover_schema", {"sourceId": source_id})
    sync_catalog = build_sync_catalog(discover, stream_name, stream_alias)
    created = client.call(
        "/connections/create",
        {
            "name": f"{name} → ClickHouse",
            "sourceId": source_id,
            "destinationId": destination_id,
            "workspaceId": workspace_id,
            "namespaceDefinition": "customformat",
            "namespaceFormat": "analytics",
            "prefix": table_prefix,
            "status": "active",
            "scheduleType": "basic",
            "scheduleData": {"basicSchedule": {"units": 15, "timeUnit": "minutes"}},
            "syncCatalog": sync_catalog,
        },
    )
    print(f"Created connection: {created['connectionId']}")
    return created["connectionId"]


def update_env_connection_ids(env_path: Path, new_ids: list[str]) -> None:
    text = env_path.read_text() if env_path.exists() else ""
    existing: list[str] = []
    match = re.search(r"^AIRBYTE_CONNECTION_IDS=(.*)$", text, re.M)
    if match and match.group(1).strip():
        existing = [item.strip() for item in match.group(1).split(",") if item.strip()]
    for item in new_ids:
        if item and item not in existing:
            existing.append(item)
    line = "AIRBYTE_CONNECTION_IDS=" + ",".join(existing)
    if match:
        text = re.sub(r"^AIRBYTE_CONNECTION_IDS=.*$", line, text, flags=re.M)
    else:
        text += f"\n{line}\n"
    env_path.write_text(text)
    print(line)


def find_source_definition(client: AirbyteClient, workspace_id: str, repo: str, name: str) -> str:
    listed = client.call("/source_definitions/list_for_workspace", {"workspaceId": workspace_id})
    for item in listed.get("sourceDefinitions", []):
        if item.get("dockerRepository") == repo and item.get("name") == name:
            return item["sourceDefinitionId"]
    return register_connector(client, workspace_id, repo, name)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    env = load_env(root / ".env")
    host = env.get("AIRBYTE_HOST", "content.netvolk.online")
    vk_only = "--vk-only" in sys.argv
    dzen_only = "--dzen-only" in sys.argv
    if vk_only and dzen_only:
        print("Use only one of --vk-only or --dzen-only")
        return 1
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    vk_config_path = Path(args[0]) if len(args) > 0 else root / "secrets" / "source-vk-config.json"
    dzen_config_path = Path(args[1]) if len(args) > 1 else root / "secrets" / "source-dzen-config.json"

    vk_config = json.loads(vk_config_path.read_text()) if not dzen_only else {}
    dzen_config = json.loads(dzen_config_path.read_text()) if not vk_only else {}

    email = env.get("AIRBYTE_USERNAME", "")
    password = env.get("AIRBYTE_PASSWORD", "")
    client_id = env.get("AIRBYTE_CLIENT_ID", "")
    client_secret = env.get("AIRBYTE_CLIENT_SECRET", "")
    if not client_id or not client_secret or not email or not password:
        ab_email, ab_pass, ab_cid, ab_cs = abctl_credentials()
        email = email or ab_email
        password = password or ab_pass
        client_id = client_id or ab_cid
        client_secret = client_secret or ab_cs
    if not client_id or not client_secret:
        print("Missing Airbyte client credentials")
        return 1

    print("==> Build connector images")
    if os.environ.get("SKIP_CONNECTOR_BUILD") != "1":
        build_targets = ["source-vk"] if vk_only else ["source-dzen"] if dzen_only else ["source-vk", "source-dzen"]
        subprocess.check_call(["docker", "compose", "--profile", "build-connectors", "build", *build_targets], cwd=root)
    cluster = env.get("AIRBYTE_KIND_CLUSTER", "airbyte-abctl")
    if subprocess.call(["bash", "-lc", "command -v kind >/dev/null"], cwd=root) == 0:
        subprocess.check_call(["kind", "load", "docker-image", "airbyte/source-vk:dev", "-n", cluster])
        if not vk_only:
            subprocess.check_call(["kind", "load", "docker-image", "airbyte/source-dzen:dev", "-n", cluster])
    else:
        subprocess.check_call(
            "docker save airbyte/source-vk:dev | "
            f"docker exec -i {cluster}-control-plane ctr -n=k8s.io images import -",
            shell=True,
        )

    client = AirbyteClient(
        host,
        client_id,
        client_secret,
        workspace_id=env.get("AIRBYTE_WORKSPACE_ID", "3f56ead9-e8a3-496d-a96d-98fd18e7d52c"),
        email=email,
        password=password,
    )
    workspace_id = client.workspace_id_or_fetch()
    destination_id = find_destination(client, workspace_id)
    print(f"Workspace: {workspace_id}")
    print(f"Destination: {destination_id}")

    new_ids: list[str] = []
    if vk_only or not dzen_only:
        vk_def = find_source_definition(client, workspace_id, "airbyte/source-vk", "VK Short Videos")
        vk_source = ensure_source(client, workspace_id, "VK Short Videos", vk_def, vk_config)
        vk_conn = ensure_connection(
            client, workspace_id, "VK Short Videos", vk_source, destination_id, "short_videos", "raw_vk_", "videos"
        )
        new_ids.append(vk_conn)

    if dzen_only or (not vk_only and not dzen_only):
        dzen_def = find_source_definition(client, workspace_id, "airbyte/source-dzen", "Yandex Dzen Shorts")
        dzen_source = ensure_source(client, workspace_id, "Yandex Dzen Shorts", dzen_def, dzen_config)
        dzen_conn = ensure_connection(
            client, workspace_id, "Yandex Dzen Shorts", dzen_source, destination_id, "shorts", "raw_dzen_"
        )
        new_ids.append(dzen_conn)

    for conn_id in new_ids:
        try:
            client.call("/connections/sync", {"connectionId": conn_id})
            print(f"Sync triggered: {conn_id}")
        except RuntimeError as exc:
            print(f"Sync warning for {conn_id}: {exc}")

    update_env_connection_ids(root / ".env", new_ids)
    app_port = env.get("APP_PORT", "8090")
    print(f"Done. Refresh dashboard: curl -X POST http://127.0.0.1:{app_port}/api/refresh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
