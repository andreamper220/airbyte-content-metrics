from __future__ import annotations

from typing import Any, Optional

from app.config import settings
from app.db import query
from app.dzen_meta import normalize_publication_id, resolve_dzen_video
from app.queries import VIDEO_DETAIL

RAW_DZEN_METRICS = """
SELECT
    coalesce(publication_id, '') AS publication_id,
    coalesce(title, '') AS title,
    coalesce(url, '') AS url,
    toUInt64(coalesce(views, 0)) AS views,
    toUInt64(coalesce(likes, 0)) AS likes,
    toUInt64(coalesce(comments, 0)) AS comments,
    coalesce(published_at, 0) AS published_at
FROM analytics.raw_dzen_shorts
WHERE publication_id IN ({ids:Array(String)})
ORDER BY _airbyte_extracted_at DESC
LIMIT 1
"""


def _video_id_candidates(platform: str, video_id: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    def add(value: str) -> None:
        value = (value or "").strip()
        if not value or value in seen:
            return
        seen.add(value)
        ordered.append(value)

    add(video_id)
    if platform == "dzen":
        add(normalize_publication_id(video_id))
        if not video_id.startswith("gif:"):
            add(f"gif:{video_id}")
            add(f"gif:{normalize_publication_id(video_id)}")


    return ordered


def _apply_resolved(row: dict[str, Any], resolved: dict[str, Any], effective_id: str) -> None:
    if resolved.get("title"):
        row["title"] = resolved["title"]
    if resolved.get("url"):
        row["url"] = resolved["url"]
    if resolved.get("image"):
        row["image"] = resolved["image"]
    if resolved.get("hls"):
        row["hls"] = resolved["hls"]
    published = int(resolved.get("published_at") or 0)
    existing = row.get("published_at")
    existing_ts = 0
    if isinstance(existing, (int, float)):
        existing_ts = int(existing)
    elif existing is not None and hasattr(existing, "year"):
        existing_ts = 0 if existing.year <= 1970 else 1
    if published and not existing_ts:
        row["published_at"] = published
    row["video_id"] = effective_id


def _row_from_mart(platform: str, video_id: str) -> Optional[dict[str, Any]]:
    for candidate in _video_id_candidates(platform, video_id):
        rows = query(VIDEO_DETAIL, {"platform": platform, "video_id": candidate})
        if rows:
            return dict(rows[0])
    return None


def _row_from_dzen_raw(publication_id: str) -> Optional[dict[str, Any]]:
    pid = normalize_publication_id(publication_id)
    ids = [pid, f"gif:{pid}"]
    rows = query(RAW_DZEN_METRICS, {"ids": ids})
    if not rows:
        return None
    row = rows[0]
    published = row.get("published_at") or 0
    return {
        "platform": "dzen",
        "video_id": pid,
        "title": row.get("title") or "",
        "published_at": published,
        "url": row.get("url") or f"https://dzen.ru/shorts/{pid}",
        "views": int(row.get("views") or 0),
        "likes": int(row.get("likes") or 0),
        "comment_count": int(row.get("comments") or 0),
        "shares": 0,
        "reach": 0,
    }


def load_video(platform: str, video_id: str) -> Optional[tuple[dict[str, Any], str]]:
    platform = platform.lower()
    video_id = video_id.strip()
    if not video_id:
        return None

    row = _row_from_mart(platform, video_id)
    effective_id = video_id

    if platform == "dzen":
        resolved = resolve_dzen_video(
            video_id,
            (row or {}).get("url") or "",
            (row or {}).get("title") or "",
            settings.dzen_channel_name or None,
        )
        if resolved:
            effective_id = str(resolved.get("video_id") or effective_id)
            if not row:
                row = _row_from_mart(platform, effective_id) or _row_from_dzen_raw(effective_id)
            if not row:
                row = {
                    "platform": "dzen",
                    "video_id": effective_id,
                    "title": resolved.get("title") or "",
                    "published_at": resolved.get("published_at") or 0,
                    "url": resolved.get("url") or f"https://dzen.ru/shorts/{effective_id}",
                    "views": 0,
                    "likes": 0,
                    "comment_count": 0,
                    "shares": 0,
                    "reach": 0,
                }
            _apply_resolved(row, resolved, effective_id)
        elif row:
            effective_id = str(row.get("video_id") or video_id)
    elif row:
        effective_id = str(row.get("video_id") or video_id)

    if not row:
        return None
    return row, effective_id
