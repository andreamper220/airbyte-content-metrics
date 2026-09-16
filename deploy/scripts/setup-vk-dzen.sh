#!/usr/bin/env bash
# Configure VK + Dzen sources in Airbyte and create ClickHouse connections.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing deploy/.env"
  exit 1
fi

# shellcheck disable=SC1091
set -a && source .env && set +a

VK_CONFIG="${1:-$ROOT/secrets/source-vk-config.json}"
DZEN_CONFIG="${2:-$ROOT/secrets/source-dzen-config.json}"

for f in "$VK_CONFIG" "$DZEN_CONFIG"; do
  if [[ ! -f "$f" ]]; then
    echo "Missing config: $f"
    exit 1
  fi
done

AB_HOST="${AIRBYTE_HOST:-content.netvolk.online}"
AB_PORT="${AIRBYTE_PORT:-8091}"
AB_BASE="http://127.0.0.1:18091"
AB_API="$AB_BASE/api/v1"

if [[ -z "${AIRBYTE_CLIENT_ID:-}" || -z "${AIRBYTE_CLIENT_SECRET:-}" ]]; then
  CREDS="$(abctl local credentials 2>/dev/null || true)"
  AIRBYTE_CLIENT_ID="$(echo "$CREDS" | sed -n 's/.*Client-Id: //p' | head -1 | tr -d '[:space:]')"
  AIRBYTE_CLIENT_SECRET="$(echo "$CREDS" | sed -n 's/.*Client-Secret: //p' | head -1 | tr -d '[:space:]')"
fi

if [[ -z "$AIRBYTE_CLIENT_ID" || -z "$AIRBYTE_CLIENT_SECRET" ]]; then
  echo "Set AIRBYTE_CLIENT_ID and AIRBYTE_CLIENT_SECRET in .env or ensure abctl works"
  exit 1
fi

ab_api() {
  local method="$1"
  local path="$2"
  local data="${3:-{}}"
  curl -sfS -X "$method" \
    -H "Host: $AB_HOST" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$data" \
    "$AB_API$path"
}

echo "==> Airbyte API token"
TOKEN="$(curl -sfS -H "Host: $AB_HOST" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$AIRBYTE_CLIENT_ID\",\"client_secret\":\"$AIRBYTE_CLIENT_SECRET\"}" \
  "$AB_API/applications/token" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')"

WORKSPACE_ID="$(ab_api POST /workspaces/list '{}' | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["workspaces"][0]["workspaceId"])')"
echo "Workspace: $WORKSPACE_ID"

DEST_ID="$(ab_api POST /destinations/list "{\"workspaceId\":\"$WORKSPACE_ID\"}" | python3 -c '
import sys, json
dests = json.load(sys.stdin).get("destinations", [])
for d in dests:
    if "clickhouse" in d.get("destinationName", "").lower():
        print(d["destinationId"]); break
else:
    print(dests[0]["destinationId"] if dests else "")
')"
if [[ -z "$DEST_ID" ]]; then
  echo "No ClickHouse destination found in Airbyte. Create it first."
  exit 1
fi
echo "Destination: $DEST_ID"

register_connector() {
  local image="$1"
  local name="$2"
  ab_api POST /source_definitions/create_custom "{\"workspaceId\":\"$WORKSPACE_ID\",\"sourceDefinition\":{\"name\":\"$name\",\"dockerRepository\":\"$image\",\"dockerImageTag\":\"dev\",\"documentationUrl\":\"https://example.com\"}}" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["sourceDefinitionId"])'
}

ensure_source() {
  local name="$1"
  local definition_id="$2"
  local config_file="$3"
  local stream_name="$4"
  local table_prefix="$5"

  local existing
  existing="$(ab_api POST /sources/list "{\"workspaceId\":\"$WORKSPACE_ID\"}" | python3 -c "
import sys, json
name = \"$name\"
for s in json.load(sys.stdin).get('sources', []):
    if s.get('name') == name:
        print(s['sourceId'])
        break
")"

  local source_id
  if [[ -n "$existing" ]]; then
    source_id="$existing"
    echo "Source exists: $name ($source_id)"
  else
    local cfg
    cfg="$(python3 -c 'import json; print(json.dumps(json.load(open("'"$config_file"'"))))')"
    source_id="$(ab_api POST /sources/create "{\"name\":\"$name\",\"sourceDefinitionId\":\"$definition_id\",\"workspaceId\":\"$WORKSPACE_ID\",\"connectionConfiguration\":$cfg}" \
      | python3 -c 'import sys,json; print(json.load(sys.stdin)["sourceId"])')"
    echo "Created source: $name ($source_id)"
  fi

  local discover
  discover="$(ab_api POST /sources/discover_schema "{\"sourceId\":\"$source_id\"}")"

  local conn_existing
  conn_existing="$(ab_api POST /connections/list "{\"workspaceId\":\"$WORKSPACE_ID\"}" | python3 -c "
import sys, json
sid = \"$source_id\"
for c in json.load(sys.stdin).get('connections', []):
    if c.get('sourceId') == sid:
        print(c['connectionId'])
        break
")"

  if [[ -n "$conn_existing" ]]; then
    echo "Connection exists: $conn_existing"
    echo "$conn_existing"
    return
  fi

  local sync_catalog
  sync_catalog="$(DISCOVER="$discover" STREAM="$stream_name" TABLE="$table_prefix" python3 <<'PY'
import json, os
catalog = json.loads(os.environ["DISCOVER"])["catalog"]
stream = os.environ["STREAM"]
table = os.environ["TABLE"]
selected = []
for s in catalog.get("streams", []):
    if s["stream"]["name"] == stream:
        s["config"] = {
            "syncMode": "incremental",
            "destinationSyncMode": "append",
            "cursorField": s["stream"].get("default_cursor_field") or [],
            "primaryKey": s["stream"].get("source_defined_primary_key") or [],
            "aliasName": stream,
            "selected": True,
        }
        selected.append(s)
        break
print(json.dumps({
    "streams": selected,
    "namespaceDefinition": "customformat",
    "namespaceFormat": "analytics",
    "prefix": table,
}))
PY
)"

  local connection_id
  connection_id="$(ab_api POST /connections/create "{
    \"name\":\"$name → ClickHouse\",
    \"sourceId\":\"$source_id\",
    \"destinationId\":\"$DEST_ID\",
    \"workspaceId\":\"$WORKSPACE_ID\",
    \"namespaceDefinition\":\"customformat\",
    \"namespaceFormat\":\"analytics\",
    \"prefix\":\"$table_prefix\",
    \"status\":\"active\",
    \"scheduleType\":\"basic\",
    \"scheduleData\":{\"basicSchedule\":{\"units\":6,\"timeUnit\":\"hours\"}},
    \"syncCatalog\":$sync_catalog
  }" | python3 -c 'import sys,json; print(json.load(sys.stdin)["connectionId"])')"
  echo "Created connection: $connection_id"
  echo "$connection_id"
}

echo "==> Build connector images"
docker compose --profile build-connectors build source-vk source-dzen
CLUSTER="${AIRBYTE_KIND_CLUSTER:-airbyte-abctl}"
if command -v kind >/dev/null 2>&1; then
  kind load docker-image airbyte/source-vk:dev -n "$CLUSTER"
  kind load docker-image airbyte/source-dzen:dev -n "$CLUSTER"
fi

echo "==> Register custom connectors"
VK_DEF="$(register_connector "airbyte/source-vk" "VK Short Videos")"
DZEN_DEF="$(register_connector "airbyte/source-dzen" "Yandex Dzen Shorts")"
echo "VK definition: $VK_DEF"
echo "Dzen definition: $DZEN_DEF"

echo "==> Sources and connections"
VK_CONN="$(ensure_source "VK Short Videos" "$VK_DEF" "$VK_CONFIG" "short_videos" "raw_vk_")"
DZEN_CONN="$(ensure_source "Yandex Dzen Shorts" "$DZEN_DEF" "$DZEN_CONFIG" "shorts" "raw_dzen_")"

echo "==> Trigger initial sync"
ab_api POST /connections/sync "{\"connectionId\":\"$VK_CONN\"}" >/dev/null || true
ab_api POST /connections/sync "{\"connectionId\":\"$DZEN_CONN\"}" >/dev/null || true

echo "==> Update AIRBYTE_CONNECTION_IDS in .env"
python3 <<PY
from pathlib import Path
import re
env = Path("$ROOT/.env")
text = env.read_text()
ids = ["$VK_CONN", "$DZEN_CONN"]
existing = []
m = re.search(r'^AIRBYTE_CONNECTION_IDS=(.*)$', text, re.M)
if m and m.group(1).strip():
    existing = [x.strip() for x in m.group(1).split(',') if x.strip()]
for i in ids:
    if i and i not in existing:
        existing.append(i)
new = ','.join(existing)
if m:
    text = re.sub(r'^AIRBYTE_CONNECTION_IDS=.*$', f'AIRBYTE_CONNECTION_IDS={new}', text, flags=re.M)
else:
    text += f'\nAIRBYTE_CONNECTION_IDS={new}\n'
env.write_text(text)
print('AIRBYTE_CONNECTION_IDS=' + new)
PY

echo "Done. Refresh dashboard: curl -X POST http://127.0.0.1:${APP_PORT:-8090}/api/refresh"
