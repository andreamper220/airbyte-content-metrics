#!/usr/bin/env python3
import importlib.util
from pathlib import Path

p = Path("/var/www/content/deploy/scripts/setup-vk-dzen.py")
spec = importlib.util.spec_from_file_location("setup", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
root = Path("/var/www/content/deploy")
env = mod.load_env(root / ".env")
client = mod.AirbyteClient(
    env.get("AIRBYTE_HOST", "content.netvolk.online"),
    env["AIRBYTE_CLIENT_ID"],
    env["AIRBYTE_CLIENT_SECRET"],
    workspace_id=env.get("AIRBYTE_WORKSPACE_ID", "3f56ead9-e8a3-496d-a96d-98fd18e7d52c"),
    email=env.get("AIRBYTE_USERNAME", ""),
    password=env.get("AIRBYTE_PASSWORD", ""),
)
ws = client.workspace_id_or_fetch()
for conn in client.call("/connections/list", {"workspaceId": ws}).get("connections", []):
    if "Dzen" in conn.get("name", ""):
        client.call("/connections/sync", {"connectionId": conn["connectionId"]})
        print("sync", conn["connectionId"])
