#!/usr/bin/env python3
import json
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

print("=== ClickHouse ===")
for q in [
    "SELECT count() FROM analytics.raw_vk_videos",
    "SELECT count() FROM analytics.raw_dzen_shorts",
    "SELECT platform, count() FROM analytics.mart_videos GROUP BY platform ORDER BY platform",
    "SHOW TABLES FROM analytics LIKE 'raw_vk%'",
]:
    out = subprocess.check_output(
        ["docker", "exec", "content-metrics-clickhouse-1", "clickhouse-client", "--query", q],
        text=True,
    )
    print(q, "->", out.strip())

cfg = json.loads(Path("/var/www/content/deploy/secrets/source-vk-config.json").read_text())
params = urllib.parse.urlencode(
    {"access_token": cfg["access_token"], "owner_id": cfg["owner_id"], "count": 100, "v": "5.199"}
)
with urllib.request.urlopen(f"https://api.vk.com/method/video.get?{params}", timeout=30) as r:
    data = json.loads(r.read())
if "error" in data:
    print("VK API error", data["error"])
else:
    items = data["response"]["items"]
    total = data["response"].get("count", len(items))
    max_d = int(cfg.get("max_short_duration_seconds", 180))
    short = [v for v in items if int(v.get("duration") or 0) <= max_d or int(v.get("duration") or 0) <= 0]
    print(f"VK video.get: total={total}, page_items={len(items)}, short<={max_d}s on page={len(short)}")
    for v in items[:5]:
        print(" ", v.get("id"), "dur", v.get("duration"), "type", v.get("type"), (v.get("title") or "")[:40])

print("=== Dzen public feed ===")
dzen = json.loads(Path("/var/www/content/deploy/secrets/source-dzen-config.json").read_text())
ch = dzen.get("channel_name", "generator_video")
url = f"https://dzen.ru/api/v3/launcher/more?channel_name={ch}&country_code=ru"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as r:
    feed = json.loads(r.read())
items = feed.get("items") or []
print(f"channel={ch} items={len(items)}")
for it in items[:3]:
    link = it.get("link") or it.get("url") or ""
    print(" ", link[:80], it.get("type"), it.get("title", "")[:30])
