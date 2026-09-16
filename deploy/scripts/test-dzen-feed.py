#!/usr/bin/env python3
import json
import re
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

for url in [
    "https://dzen.ru/api/v3/launcher/more?channel_name=generator_video&country_code=ru",
    "https://dzen.ru/api/v3/launcher/export?channel_name=generator_video",
]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8", errors="replace")
        print("URL", url[:70])
        print(" len", len(body))
        if body.startswith("{"):
            d = json.loads(body)
            print(" keys", list(d.keys())[:8], "items", len(d.get("items") or []))
        print()
    except Exception as e:
        print(url, e)

req = urllib.request.Request("https://dzen.ru/generator_video", headers={"User-Agent": UA})
with urllib.request.urlopen(req, timeout=30) as r:
    html = r.read().decode("utf-8", errors="replace")
print("html len", len(html))
print("shorts urls", re.findall(r"https://dzen\\.ru/shorts/[\\w-]+", html)[:5])
print("video ids", re.findall(r'"publicationId"\\s*:\\s*"([^"]+)"', html)[:5])
print("type short", "shortVideo" in html or "SHORT" in html)
