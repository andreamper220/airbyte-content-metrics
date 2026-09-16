#!/usr/bin/env python3
import json
import urllib.parse
import urllib.request
from pathlib import Path

cfg = json.loads(Path("/var/www/content/deploy/secrets/source-vk-config.json").read_text())
p = urllib.parse.urlencode(
    {
        "access_token": cfg["access_token"],
        "owner_id": cfg["owner_id"],
        "count": 20,
        "filter": "owner",
        "v": "5.199",
    }
)
with urllib.request.urlopen(f"https://api.vk.com/method/wall.get?{p}", timeout=30) as r:
    data = json.loads(r.read())
if "error" in data:
    print("wall error", data["error"])
    raise SystemExit(1)
items = (data.get("response") or {}).get("items") or []
print("wall posts", len(items))
for post in items:
    for att in post.get("attachments") or []:
        if att.get("type") != "video":
            continue
        v = att["video"]
        print(" video", v.get("id"), "dur", v.get("duration"), "type", v.get("type"), (v.get("title") or "")[:50])
