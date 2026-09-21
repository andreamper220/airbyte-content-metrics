from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from functools import lru_cache
from typing import Any, Mapping, Optional

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
SHORTS_PATH = re.compile(r"/shorts/([^/?#]+)")
GENERIC_TITLES = frozenset({"ролики", "shorts", "видео", "ролик", "short"})


def dzen_short_id_from_url(url: str | None) -> str:
    if not url:
        return ""
    match = SHORTS_PATH.search(url)
    return match.group(1) if match else ""


def is_block_publication_id(publication_id: str) -> bool:
    return bool(publication_id) and publication_id.startswith("-") and publication_id[1:].isdigit()


def normalize_publication_id(publication_id: str) -> str:
    if publication_id.startswith("gif:"):
        return publication_id.split(":", 1)[1]
    return publication_id


def is_generic_title(title: str | None) -> bool:
    if not title or not str(title).strip():
        return True
    return str(title).strip().lower() in GENERIC_TITLES


def shorts_player_url(publication_id: str, url: str | None = None) -> str:
    from_url = dzen_short_id_from_url(url)
    if from_url and not is_block_publication_id(from_url):
        return f"https://dzen.ru/shorts/{from_url}"
    pid = normalize_publication_id(publication_id)
    if pid and not is_block_publication_id(pid):
        return f"https://dzen.ru/shorts/{pid}"
    return url or ""


@lru_cache(maxsize=16)
def _fetch_export(channel_name: str) -> Mapping[str, Any]:
    channel = channel_name.strip().lstrip("@")
    api_url = f"https://dzen.ru/api/v3/launcher/export?channel_name={channel}&country_code=ru"
    req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read())


def _walk_nodes(payload: Any):
    if isinstance(payload, list):
        for entry in payload:
            yield from _walk_nodes(entry)
        return
    if not isinstance(payload, dict):
        return
    yield payload
    for key in ("items", "publications", "entries", "cards", "feed", "data", "result"):
        if key in payload:
            yield from _walk_nodes(payload[key])


def _node_to_short(node: Mapping[str, Any]) -> Optional[dict[str, Any]]:
    item_type = str(node.get("item_type") or node.get("type") or "").lower()
    if item_type in {"channel_block_shorts", "channel_short_video_floor"}:
        return None
    if item_type != "short_video" and node.get("type") != "short_video":
        link = str(node.get("share_link") or node.get("link") or node.get("url") or "")
        if "/shorts/" not in link:
            return None

    publication_id = str(node.get("publication_object_id") or node.get("publicationObjectId") or "").strip()
    link = str(node.get("share_link") or node.get("ext_link") or node.get("link") or node.get("url") or "")
    if not publication_id:
        publication_id = dzen_short_id_from_url(link)
    publication_id = normalize_publication_id(publication_id)
    if not publication_id or is_block_publication_id(publication_id):
        return None

    title = str(node.get("title") or node.get("text") or "").strip()
    if is_generic_title(title):
        return None

    published_at = 0
    raw_date = node.get("publication_date") or node.get("publishTime")
    if raw_date is not None:
        try:
            published_at = int(raw_date)
            if published_at > 10_000_000_000:
                published_at //= 1000
        except (TypeError, ValueError):
            published_at = 0

    player_url = shorts_player_url(publication_id, link)
    return {
        "video_id": publication_id,
        "title": title,
        "url": player_url or link,
        "published_at": published_at,
        "image": _cover_url(node),
        "hls": _hls_url(node),
    }


def _hls_url(node: Mapping[str, Any]) -> str:
    video = node.get("video") or {}
    if not isinstance(video, dict):
        return ""
    for item in video.get("oneVideoStreams") or []:
        if isinstance(item, dict) and item.get("type") == "hls" and isinstance(item.get("url"), str):
            return item["url"]
    for stream in video.get("streams") or []:
        if isinstance(stream, str) and ".m3u8" in stream:
            return stream
    video_id = video.get("id")
    if isinstance(video_id, str) and ".m3u8" in video_id:
        return video_id
    return ""


def _cover_url(node: Mapping[str, Any]) -> str:
    image = node.get("common_image") or {}
    if isinstance(image, dict):
        template = image.get("url_template")
        if isinstance(template, str) and template:
            return template.replace("{namespace}", str(image.get("namespace") or "zen_doc")).replace(
                "{size}", "scale_720"
            )
    previews = (node.get("video") or {}).get("previews") if isinstance(node.get("video"), dict) else None
    if isinstance(previews, dict):
        for key in ("720", "480", "144"):
            value = previews.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return value
    return _extract_image(node)


def _extract_image(item: Mapping[str, Any]) -> str:
    for key in ("image", "imageUrl", "image_url", "preview", "thumbnail", "cover", "picture", "poster"):
        value = item.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
        if isinstance(value, dict):
            for nested_key in ("url", "src", "orig", "main"):
                nested = value.get(nested_key)
                if isinstance(nested, str) and nested.startswith("http"):
                    return nested
    return ""


def dzen_comment_meta(
    video_id: str,
    channel_name: str | None,
) -> Optional[dict[str, Any]]:
    pid = normalize_publication_id(video_id)
    if not channel_name:
        if pid:
            return {"video_id": pid, "document_id": f"gif:{pid}", "token": "", "publisher_id": ""}
        return None
    try:
        export = _fetch_export(channel_name)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return {"video_id": pid, "document_id": f"gif:{pid}", "token": "", "publisher_id": ""} if pid else None

    for node in _walk_nodes(export):
        node_pid = normalize_publication_id(
            str(node.get("publication_object_id") or node.get("publication_id") or "")
        )
        document_id = str(node.get("comments_document_id") or "")
        if node_pid == pid or document_id in {video_id, f"gif:{pid}", pid}:
            return {
                "video_id": node_pid or pid,
                "document_id": document_id or f"gif:{pid}",
                "token": str(node.get("comments_token") or ""),
                "publisher_id": str(node.get("publisher_id") or ""),
            }
    if pid:
        return {"video_id": pid, "document_id": f"gif:{pid}", "token": "", "publisher_id": ""}
    return None


def resolve_dzen_video(
    video_id: str,
    url: str | None,
    title: str | None,
    channel_name: str | None,
    *,
    fallback: bool = True,
) -> Optional[dict[str, Any]]:
    url_id = dzen_short_id_from_url(url)
    pid = normalize_publication_id(video_id)
    if not channel_name:
        if url_id and not is_block_publication_id(url_id):
            return {"video_id": url_id, "title": title or "", "url": shorts_player_url(url_id, url)}
        return None

    try:
        export = _fetch_export(channel_name)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None

    block_match: Optional[dict[str, Any]] = None
    id_match: Optional[dict[str, Any]] = None
    first_short: Optional[dict[str, Any]] = None

    for node in _walk_nodes(export):
        if str(node.get("id") or "") == video_id and isinstance(node.get("items"), list):
            for child in node["items"]:
                if isinstance(child, dict):
                    parsed = _node_to_short(child)
                    if parsed:
                        block_match = parsed
                        break
        parsed = _node_to_short(node)
        if not parsed:
            continue
        if first_short is None:
            first_short = parsed
        if parsed["video_id"] == pid or (url_id and parsed["video_id"] == url_id):
            id_match = parsed

    if fallback:
        return block_match or id_match or first_short
    return block_match or id_match
