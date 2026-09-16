#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

root = Path("/var/www/content/deploy")
cfg_path = root / "secrets/source-vk-config.json"
disc_path = root / "secrets/vk-discover.json"
cat_path = root / "secrets/vk-read-catalog.json"

subprocess.check_call(
    [
        "docker",
        "run",
        "--rm",
        "--user",
        "root",
        "-v",
        f"{cfg_path}:/config.json:ro",
        "airbyte/source-vk:dev",
        "discover",
        "--config",
        "/config.json",
    ],
    stdout=disc_path.open("w"),
)
disc = json.loads(disc_path.read_text())
for stream in disc["catalog"]["streams"]:
    name = stream.get("name") or stream.get("stream", {}).get("name")
    if name == "short_videos":
        configured = {
            "stream": stream if "json_schema" in stream else stream["stream"],
            "sync_mode": "full_refresh",
            "destination_sync_mode": "append",
        }
        cat_path.write_text(json.dumps({"streams": [configured]}))
        break
else:
    raise SystemExit("short_videos not in discover")

proc = subprocess.run(
    [
        "docker",
        "run",
        "--rm",
        "--user",
        "root",
        "-v",
        f"{cfg_path}:/config.json:ro",
        "-v",
        f"{cat_path}:/catalog.json:ro",
        "airbyte/source-vk:dev",
        "read",
        "--config",
        "/config.json",
        "--catalog",
        "/catalog.json",
    ],
    capture_output=True,
    text=True,
    timeout=180,
)
records = [ln for ln in proc.stdout.splitlines() if '"type": "RECORD"' in ln or '"type":"RECORD"' in ln]
print("RECORD count:", len(records))
for ln in records[:3]:
    print(ln[:600])
if proc.returncode != 0:
    print("exit", proc.returncode)
print(proc.stderr[-1000:] if proc.stderr else "")
