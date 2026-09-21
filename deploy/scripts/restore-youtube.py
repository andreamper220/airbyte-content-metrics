#!/usr/bin/env python3
"""Restore analytics.video from YouTube Data API after an empty overwrite sync."""
from __future__ import annotations

import json
import subprocess
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(errors="replace").splitlines():
        if not line.strip() or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def yt_get(path: str, params: dict[str, str]) -> dict:
    url = f"https://www.googleapis.com/youtube/v3/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read())


def dumps(value) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def main() -> int:
    env = load_env(Path("/var/www/content/deploy/.env"))
    yt_env = load_env(Path("/var/www/content/deploy/secrets/youtube.env"))
    key = yt_env.get("YOUTUBE_API_KEY") or env.get("YOUTUBE_API_KEY") or ""
    channel_id = yt_env.get("YOUTUBE_CHANNEL_ID") or env.get("YOUTUBE_CHANNEL_ID") or "UCTdknyWt_31mE2CPjuENIjw"
    if not key:
        print("missing youtube api key")
        return 1

    ch = yt_get("channels", {"part": "contentDetails", "id": channel_id, "key": key})
    uploads = (((ch.get("items") or [{}])[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
    if not uploads:
        print("no uploads playlist", ch.get("error"))
        return 1

    video_ids: list[str] = []
    page = ""
    while True:
        params = {"part": "snippet", "playlistId": uploads, "maxResults": "50", "key": key}
        if page:
            params["pageToken"] = page
        payload = yt_get("playlistItems", params)
        for item in payload.get("items") or []:
            vid = ((item.get("snippet") or {}).get("resourceId") or {}).get("videoId")
            if vid:
                video_ids.append(vid)
        page = payload.get("nextPageToken") or ""
        if not page:
            break
    print("playlist videos", len(video_ids))

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = []
    for offset in range(0, len(video_ids), 50):
        chunk = video_ids[offset : offset + 50]
        payload = yt_get(
            "videos",
            {
                "part": "snippet,contentDetails,statistics,player,status",
                "id": ",".join(chunk),
                "key": key,
            },
        )
        for item in payload.get("items") or []:
            snippet = item.get("snippet") or {}
            video_id = item.get("id") or ""
            rows.append(
                {
                    "_airbyte_raw_id": str(uuid.uuid4()),
                    "_airbyte_extracted_at": now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "_airbyte_meta": "{}",
                    "_airbyte_generation_id": 0,
                    "id": video_id,
                    "etag": item.get("etag"),
                    "kind": item.get("kind") or "youtube#video",
                    "tags": dumps(snippet.get("tags")),
                    "title": snippet.get("title"),
                    "player": dumps(item.get("player")),
                    "status": dumps(item.get("status")),
                    "videoId": video_id,
                    "datetime": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "channelId": snippet.get("channelId"),
                    "localized": dumps(snippet.get("localized")),
                    "categoryId": snippet.get("categoryId"),
                    "statistics": dumps(item.get("statistics")),
                    "thumbnails": dumps(snippet.get("thumbnails")),
                    "description": snippet.get("description"),
                    "publishedAt": snippet.get("publishedAt"),
                    "channelTitle": snippet.get("channelTitle"),
                    "contentDetails": dumps(item.get("contentDetails")),
                    "defaultLanguage": snippet.get("defaultLanguage"),
                    "defaultAudioLanguage": snippet.get("defaultAudioLanguage"),
                    "liveBroadcastContent": snippet.get("liveBroadcastContent"),
                }
            )
    print("detail rows", len(rows))
    if not rows:
        return 1
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    proc = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            "content-metrics-clickhouse-1",
            "clickhouse-client",
            "--query",
            "INSERT INTO analytics.video FORMAT JSONEachRow",
        ],
        input=payload.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        print("insert failed", proc.stderr.decode("utf-8", "replace")[:800])
        return proc.returncode
    count = subprocess.check_output(
        [
            "docker",
            "exec",
            "content-metrics-clickhouse-1",
            "clickhouse-client",
            "--query",
            "SELECT count(), max(publishedAt) FROM analytics.video WHERE kind='youtube#video'",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
    ).strip()
    print("youtube restored", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
