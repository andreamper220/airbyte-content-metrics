import json, urllib.request
import sys
sys.path.insert(0, "/var/www/content/airbyte-integrations/connectors/source-dzen")
from source_dzen.streams import Shorts, _walk_publication_nodes, _normalize_short

url = "https://dzen.ru/api/v3/launcher/export?channel_name=generator_video&country_code=ru"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as r:
    payload = json.loads(r.read())
items = payload.get("items") or []
print("top items", len(items))
for node in _walk_publication_nodes(payload):
    rec = _normalize_short(node)
    if rec:
        print("RECORD", rec)
        break
else:
    print("no normalized record; sample keys", list(items[0].keys()) if items else "none")
