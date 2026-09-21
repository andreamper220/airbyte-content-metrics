from __future__ import annotations

import urllib.error
import urllib.request
from urllib.parse import quote, urljoin, urlparse

from fastapi import HTTPException
from fastapi.responses import Response, StreamingResponse

from app.config import settings
from app.dzen_meta import resolve_dzen_video

_ALLOWED_HOST_SUFFIXES = (".okcdn.ru",)
_ALLOWED_HOSTS = {"okcdn.ru"}
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _host_allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    if host in _ALLOWED_HOSTS:
        return True
    return any(host.endswith(suffix) for suffix in _ALLOWED_HOST_SUFFIXES)


def _rewrite_playlist(body: str, source_url: str) -> str:
    base = source_url.rsplit("/", 1)[0] + "/"
    lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            lines.append(line)
            continue
        if stripped.startswith("http"):
            absolute = stripped
        else:
            absolute = urljoin(base, stripped)
        lines.append(f"/api/dzen/cdn?u={quote(absolute, safe='')}")
    return "\n".join(lines) + "\n"


def playlist_for_publication(video_id: str) -> Response:
    resolved = resolve_dzen_video(video_id, None, None, settings.dzen_channel_name or None)
    hls = (resolved or {}).get("hls")
    if not hls or not _host_allowed(hls):
        raise HTTPException(status_code=404, detail="Dzen stream not found")
    return fetch_cdn(hls)


def fetch_cdn(url: str) -> Response:
    if not _host_allowed(url):
        raise HTTPException(status_code=400, detail="Host not allowed")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _UA, "Referer": "https://dzen.ru/", "Origin": "https://dzen.ru"},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as upstream:
            body = upstream.read()
            content_type = upstream.headers.get("Content-Type", "")
            status = upstream.status
    except urllib.error.HTTPError as exc:
        raise HTTPException(status_code=exc.code, detail="Dzen CDN error") from exc
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail="Dzen CDN unavailable") from exc
    if status >= 400:
        raise HTTPException(status_code=status, detail="Dzen CDN error")
    if "mpegurl" in content_type or body[:7] == b"#EXTM3U" or ".m3u8" in url:
        text = body.decode("utf-8", "replace")
        rewritten = _rewrite_playlist(text, url)
        return Response(content=rewritten, media_type="application/vnd.apple.mpegurl")
    return StreamingResponse(
        iter([body]),
        media_type=content_type or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=30"},
    )
