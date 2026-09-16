#!/usr/bin/env python3
"""Push secrets/source-vk-config.json into Airbyte and trigger sync."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import importlib.util

_setup_path = Path(__file__).resolve().parent / "setup-vk-dzen.py"
_spec = importlib.util.spec_from_file_location("setup_vk_dzen", _setup_path)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
AirbyteClient = _mod.AirbyteClient
abctl_credentials = _mod.abctl_credentials
load_env = _mod.load_env


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    env = load_env(root / ".env")
    host = env.get("AIRBYTE_HOST", "content.netvolk.online")
    email = env.get("AIRBYTE_USERNAME", "")
    password = env.get("AIRBYTE_PASSWORD", "")
    client_id = env.get("AIRBYTE_CLIENT_ID", "")
    client_secret = env.get("AIRBYTE_CLIENT_SECRET", "")
    if not client_id:
        _, _, client_id, client_secret = abctl_credentials()
    cfg = json.loads((root / "secrets" / "source-vk-config.json").read_text())
    cfg["max_short_duration_seconds"] = min(int(cfg.get("max_short_duration_seconds", 600)), 600)

    client = AirbyteClient(
        host,
        client_id,
        client_secret,
        workspace_id=env.get("AIRBYTE_WORKSPACE_ID", "3f56ead9-e8a3-496d-a96d-98fd18e7d52c"),
        email=email,
        password=password,
    )
    ws = client.workspace_id_or_fetch()
    sources = client.call("/sources/list", {"workspaceId": ws}).get("sources", [])
    vk = next((s for s in sources if "vk" in s.get("name", "").lower()), None)
    if not vk:
        print("VK source not found")
        return 1
    client.call(
        "/sources/update",
        {
            "sourceId": vk["sourceId"],
            "connectionConfiguration": cfg,
            "name": vk["name"],
        },
    )
    print("Updated source", vk["sourceId"])
    conns = client.call("/connections/list", {"workspaceId": ws}).get("connections", [])
    conn = next((c for c in conns if c.get("sourceId") == vk["sourceId"]), None)
    if conn:
        client.call("/connections/sync", {"connectionId": conn["connectionId"]})
        print("Sync triggered", conn["connectionId"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
