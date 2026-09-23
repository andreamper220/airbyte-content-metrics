#!/usr/bin/env python3
"""Register TikTok Business source and ClickHouse connection."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

SIBLING = Path(__file__).resolve().parent / "setup-vk-dzen.py"
_spec = importlib.util.spec_from_file_location("setup_vk_dzen", SIBLING)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def load_image(cluster: str) -> None:
    image = "airbyte/source-tiktok-business:dev"
    if subprocess.call(["bash", "-lc", "command -v kind >/dev/null"]) == 0:
        subprocess.check_call(["kind", "load", "docker-image", image, "-n", cluster])
        return
    subprocess.check_call(
        f"docker save {image} | docker exec -i {cluster}-control-plane ctr -n=k8s.io images import -",
        shell=True,
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    env = mod.load_env(root / ".env")
    host = env.get("AIRBYTE_HOST", "content.netvolk.online")
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "secrets" / "source-tiktok-config.json"
    config = json.loads(config_path.read_text())

    email = env.get("AIRBYTE_USERNAME", "")
    password = env.get("AIRBYTE_PASSWORD", "")
    client_id = env.get("AIRBYTE_CLIENT_ID", "")
    client_secret = env.get("AIRBYTE_CLIENT_SECRET", "")
    if not client_id or not client_secret or not email or not password:
        ab_email, ab_pass, ab_cid, ab_cs = mod.abctl_credentials()
        email = email or ab_email
        password = password or ab_pass
        client_id = client_id or ab_cid
        client_secret = client_secret or ab_cs
    if not client_id or not client_secret:
        print("Missing Airbyte client credentials")
        return 1

    print("==> Build connector image")
    if os.environ.get("SKIP_CONNECTOR_BUILD") != "1":
        subprocess.check_call(
            ["docker", "compose", "--profile", "build-connectors", "build", "source-tiktok-business"],
            cwd=root,
        )
    cluster = env.get("AIRBYTE_KIND_CLUSTER", "airbyte-abctl")
    print("==> Load image into kind")
    load_image(cluster)

    client = mod.AirbyteClient(
        host,
        client_id,
        client_secret,
        workspace_id=env.get("AIRBYTE_WORKSPACE_ID", "3f56ead9-e8a3-496d-a96d-98fd18e7d52c"),
        email=email,
        password=password,
    )
    workspace_id = client.workspace_id_or_fetch()
    destination_id = mod.find_destination(client, workspace_id)
    print(f"Workspace: {workspace_id}")
    print(f"Destination: {destination_id}")

    definition_id = mod.find_source_definition(
        client, workspace_id, "airbyte/source-tiktok-business", "TikTok Business (Organic)"
    )
    source_id = mod.ensure_source(client, workspace_id, "TikTok Business (Organic)", definition_id, config)
    conn_id = mod.ensure_connection(
        client,
        workspace_id,
        "TikTok Business (Organic)",
        source_id,
        destination_id,
        "videos",
        "raw_tiktok_",
    )
    try:
        client.call("/connections/sync", {"connectionId": conn_id})
        print(f"Sync triggered: {conn_id}")
    except RuntimeError as exc:
        print(f"Sync warning: {exc}")
    mod.update_env_connection_ids(root / ".env", [conn_id])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
