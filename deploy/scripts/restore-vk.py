#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CFG = Path("/var/www/content/deploy/secrets/source-vk-config.json")
MAX_DURATION = 180


def vk_call(token: str, method: str, extra: dict) -> dict:
    q = urllib.parse.urlencode({"access_token": token, "v": "5.199", **extra})
    with urllib.request.urlopen(f"https://api.vk.com/method/{method}?{q}", timeout=30) as response:
        data = json.loads(response.read())
    if data.get("error"):
        err = data["error"]
        raise RuntimeError(f"{method} {err.get('error_code')} {err.get('error_msg')}")
    return data.get("response") or {}


def normalize(video: dict, owner_id: int) -> dict | None:
    if not video.get("id"):
        return None
    duration = int(video.get("duration") or 0)
    video_type = str(video.get("type") or "").lower()
    if duration > MAX_DURATION and video_type not in {"short_video", "clip", "short"}:
        return None
    owner = int(video.get("owner_id", owner_id))
    video_numeric_id = int(video["id"])
    likes = video.get("likes") or {}
    reposts = video.get("reposts") or {}
    return {
        "video_id": f"{owner}_{video_numeric_id}",
        "owner_id": owner,
        "title": video.get("title") or "",
        "description": video.get("description") or "",
        "published_at": int(video.get("date") or 0),
        "duration": duration,
        "views": int(video.get("views") or 0),
        "likes": int(likes.get("count") or 0) if isinstance(likes, dict) else int(likes or 0),
        "comments": int(video.get("comments") or 0),
        "reposts": int(reposts.get("count") or 0) if isinstance(reposts, dict) else int(reposts or 0),
        "player_url": video.get("player") or "",
        "share_url": f"https://vk.com/video{owner}_{video_numeric_id}",
        "_airbyte_extracted_at": datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
    }


def main() -> int:
    cfg = json.loads(CFG.read_text())
    token = cfg["access_token"]
    owner_id = int(cfg["owner_id"])
    seen: dict[str, dict] = {}
    offset = 0
    while True:
        data = vk_call(token, "wall.get", {"owner_id": owner_id, "count": 100, "offset": offset, "filter": "owner"})
        posts = data.get("items") or []
        for post in posts:
            for attachment in post.get("attachments") or []:
                if attachment.get("type") != "video":
                    continue
                record = normalize(attachment.get("video") or {}, owner_id)
                if record:
                    seen[record["video_id"]] = record
        total = int(data.get("count") or 0)
        offset += len(posts)
        if offset >= total or not posts:
            break
    rows = list(seen.values())
    print("vk shorts", len(rows))
    for row in sorted(rows, key=lambda item: item["published_at"], reverse=True)[:8]:
        print(row["video_id"], row["published_at"], row["duration"], row["title"][:40])
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
            "INSERT INTO analytics.raw_vk_short_videos FORMAT JSONEachRow",
        ],
        input=body.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        print("insert failed", proc.stderr.decode("utf-8", "replace")[:800])
        return proc.returncode
    # Keep compose env in sync for comments without printing the token.
    env_path = Path("/var/www/content/deploy/.env")
    lines = env_path.read_text(encoding="utf-8").splitlines()
    out = []
    replaced = False
    for line in lines:
        if line.startswith("VK_ACCESS_TOKEN="):
            out.append(f"VK_ACCESS_TOKEN={token}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"VK_ACCESS_TOKEN={token}")
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("env token updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
