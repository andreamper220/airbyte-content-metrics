#!/usr/bin/env python3
"""Pull current Dzen shorts into ClickHouse without waiting for Airbyte."""
from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CHANNEL = "generator_video"
SHORTS_PATH = re.compile(r"/shorts/([^/?#]+)")
GENERIC_TITLES = frozenset({"ролики", "shorts", "видео", "ролик", "short"})
BLOCK_ITEM_TYPES = frozenset({"channel_block_shorts", "channel_short_video_floor"})
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def first_int(*values) -> int:
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict):
            for key in ("count", "value", "total"):
                if key in value:
                    try:
                        return int(value[key])
                    except (TypeError, ValueError):
                        pass
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def extract_link(item: dict) -> str:
    for key in ("share_link", "ext_link", "link", "url", "shareLink", "publicationUrl", "canonicalUrl"):
        value = item.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value.split("?", 1)[0] if key in {"share_link", "ext_link"} else value
    return ""


def object_id_timestamp(publication_id: str) -> int:
    text = str(publication_id or "").strip()
    if text.startswith("gif:"):
        text = text.split(":", 1)[1]
    if len(text) < 8:
        return 0
    hex8 = text[:8]
    if any(char not in "0123456789abcdefABCDEF" for char in hex8):
        return 0
    timestamp = int(hex8, 16)
    if 1_000_000_000 <= timestamp <= 2_100_000_000:
        return timestamp
    return 0


def extract_publication_id(item: dict, link: str) -> str:
    for key in ("publication_object_id", "publicationObjectId", "publicationId", "publication_id", "id", "itemId", "contentId"):
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        if text.startswith("gif:"):
            return text.split(":", 1)[1]
        if key == "id" and text.startswith("-") and text[1:].isdigit():
            continue
        return text
    match = SHORTS_PATH.search(link)
    return match.group(1) if match else ""


def extract_title(item: dict) -> str:
    candidates = []
    for key in ("title", "name", "snippet", "text"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())
    for key in ("video", "content", "preview"):
        nested = item.get(key)
        if isinstance(nested, dict):
            nested_title = extract_title(nested)
            if nested_title:
                candidates.append(nested_title)
    for title in candidates:
        if title.strip().lower() not in GENERIC_TITLES:
            return title
    return candidates[0] if candidates else ""


def is_short_item(item: dict) -> bool:
    item_type = str(item.get("item_type") or item.get("type") or "").lower()
    if item_type in BLOCK_ITEM_TYPES or "block_short" in item_type:
        return False
    link = extract_link(item)
    if "/a/" in link or "/news/" in link:
        return False
    if item_type == "short_video" or item.get("type") == "short_video":
        return True
    if "/shorts/" in link:
        return True
    for key in ("type", "contentType", "cardType", "publicationType"):
        value = str(item.get(key) or "").lower()
        if "short" in value or value in {"gif", "video", "short_video", "vertical_video", "generator_video"}:
            return True
    if link and "dzen.ru" in link and extract_title(item):
        return True
    publication_id = extract_publication_id(item, link)
    return bool(publication_id and object_id_timestamp(publication_id))


def walk(payload):
    if isinstance(payload, list):
        for entry in payload:
            yield from walk(entry)
        return
    if not isinstance(payload, dict):
        return
    link = extract_link(payload)
    publication_id = extract_publication_id(payload, link)
    if link or publication_id:
        yield payload
    for key in ("items", "publications", "entries", "cards", "feed", "data", "result"):
        if key in payload:
            yield from walk(payload[key])


def normalize(item: dict) -> dict | None:
    if not is_short_item(item):
        return None
    link = extract_link(item)
    publication_id = extract_publication_id(item, link)
    if not publication_id:
        return None
    if publication_id.startswith("-") and publication_id[1:].isdigit():
        return None
    title = extract_title(item)
    if not title or title.strip().lower() in GENERIC_TITLES:
        return None
    if "/shorts/" not in link:
        link = f"https://dzen.ru/shorts/{publication_id}"
    stats = item.get("statistics") or item.get("stats") or item.get("socialInfo") or {}
    if not isinstance(stats, dict):
        stats = {}
    return {
        "publication_id": publication_id,
        "title": title,
        "published_at": object_id_timestamp(publication_id),
        "url": link,
        "views": first_int(item.get("views"), stats.get("views"), stats.get("viewCount")),
        "likes": first_int(item.get("likes"), stats.get("likes"), stats.get("likeCount")),
        "comments": first_int(item.get("comments"), stats.get("comments"), stats.get("commentCount")),
        "content_type": "short",
        "_airbyte_extracted_at": datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
    }


def fetch_export(channel: str) -> dict:
    req = urllib.request.Request(
        f"https://dzen.ru/api/v3/launcher/export?channel_name={channel}&country_code=ru",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())


def main() -> int:
    cfg = {}
    path = Path("/var/www/content/deploy/secrets/source-dzen-config.json")
    if path.exists():
        cfg = json.loads(path.read_text())
    channel = cfg.get("channel_name") or CHANNEL
    payload = fetch_export(channel)
    seen = {}
    for node in walk(payload):
        record = normalize(node)
        if record:
            seen[record["publication_id"]] = record
    rows = list(seen.values())
    print("dzen shorts", len(rows), [row["publication_id"] for row in rows])
    if not rows:
        return 1
    body = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    proc = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            "content-metrics-clickhouse-1",
            "clickhouse-client",
            "--query",
            "INSERT INTO analytics.raw_dzen_shorts FORMAT JSONEachRow",
        ],
        input=body.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        print("insert failed", proc.stderr.decode("utf-8", "replace")[:800])
        return proc.returncode
    print(
        subprocess.check_output(
            [
                "docker",
                "exec",
                "content-metrics-clickhouse-1",
                "clickhouse-client",
                "--query",
                "SELECT count(), max(published_at) FROM analytics.raw_dzen_shorts",
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
        ).strip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
