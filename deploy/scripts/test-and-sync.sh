#!/bin/bash
set -euo pipefail
CAT='{"streams":[{"stream":{"name":"short_videos","json_schema":{},"supported_sync_modes":["full_refresh"],"source_defined_primary_key":[["video_id"]]},"sync_mode":"full_refresh","destination_sync_mode":"overwrite"}]}'
echo "$CAT" | docker run --rm -i --user root \
  -v /var/www/content/deploy/secrets/source-vk-config.json:/config.json:ro \
  airbyte/source-vk:dev read --config /config.json --catalog /dev/stdin 2>/dev/null \
  | python3 -c "import sys,json; n=0
for line in sys.stdin:
  o=json.loads(line)
  if o.get('type')=='RECORD':
    n+=1
    print(o['record']['data'])
print('vk_records', n)"

echo "$CAT" | sed 's/short_videos/shorts/g; s/video_id/publication_id/g' | docker run --rm -i --user root \
  -v /var/www/content/deploy/secrets/source-dzen-config.json:/config.json:ro \
  airbyte/source-dzen:dev read --config /config.json --catalog /dev/stdin 2>/dev/null \
  | python3 -c "import sys,json; n=0
for line in sys.stdin:
  o=json.loads(line)
  if o.get('type')=='RECORD':
    n+=1
    print(o['record']['data'])
print('dzen_records', n)"

cd /var/www/content/deploy
python3 <<'PY'
import importlib.util
from pathlib import Path
p = Path("scripts/setup-vk-dzen.py")
spec = importlib.util.spec_from_file_location("setup", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
env = mod.load_env(Path(".env"))
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
    name = conn.get("name", "")
    if "VK" in name or "Dzen" in name:
        client.call("/connections/sync", {"connectionId": conn["connectionId"]})
        print("sync", name, conn["connectionId"])
PY
