from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import settings

COMMENTABLE_PLATFORMS = ("youtube", "vk", "dzen")


def _read_json(path: str) -> dict[str, Any]:
    if not path:
        return {}
    file_path = Path(path)
    if not file_path.is_file():
        return {}
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


@lru_cache
def _bundle() -> dict[str, Any]:
    return _read_json(settings.comment_credentials_path)


def _section(name: str) -> dict[str, Any]:
    raw = _bundle().get(name)
    return raw if isinstance(raw, dict) else {}


def _youtube_token_file() -> dict[str, Any]:
    path = settings.youtube_token_path or "/secrets/youtube-comment-token.json"
    return _read_json(path)


def youtube_client_id() -> str:
    stored = _youtube_token_file()
    if stored.get("refresh_token"):
        return (
            str(stored.get("client_id") or "")
            or settings.google_client_id
            or settings.youtube_client_id
            or str(_section("youtube").get("client_id") or "")
        ).strip()
    return (
        settings.youtube_client_id
        or str(_section("youtube").get("client_id") or "")
        or settings.google_client_id
    ).strip()


def youtube_client_secret() -> str:
    stored = _youtube_token_file()
    if stored.get("refresh_token"):
        return (
            settings.google_client_secret
            or settings.youtube_client_secret
            or str(_section("youtube").get("client_secret") or "")
        ).strip()
    return (
        settings.youtube_client_secret
        or str(_section("youtube").get("client_secret") or "")
        or settings.google_client_secret
    ).strip()


def youtube_refresh_token() -> str:
    token = (settings.youtube_refresh_token or str(_section("youtube").get("refresh_token") or "")).strip()
    if token:
        return token
    return str(_youtube_token_file().get("refresh_token") or "").strip()


def youtube_channel_id() -> str:
    return (settings.youtube_channel_id or str(_section("youtube").get("channel_id") or "")).strip()


def vk_credentials() -> tuple[str, int]:
    token = settings.vk_access_token or str(_section("vk").get("access_token") or "")
    owner_raw = settings.vk_owner_id or _section("vk").get("owner_id") or 0
    try:
        owner_id = int(owner_raw or 0)
    except (TypeError, ValueError):
        owner_id = 0
    if token and owner_id:
        return token.strip(), owner_id
    extra = _read_json(settings.vk_config_path)
    if not token:
        token = str(extra.get("access_token") or "")
    if not owner_id:
        try:
            owner_id = int(extra.get("owner_id") or 0)
        except (TypeError, ValueError):
            owner_id = 0
    return token.strip(), owner_id


def _parse_cookie_header(raw: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in (raw or "").split(";"):
        item = part.strip()
        if not item or "=" not in item:
            continue
        name, value = item.split("=", 1)
        name = name.strip()
        if name:
            cookies[name] = value.strip()
    return cookies


def _dzen_file() -> dict[str, Any]:
    return _read_json(settings.dzen_cookie_path)


def dzen_session_id() -> str:
    return (
        settings.dzen_session_id
        or str(_section("dzen").get("session_id") or "")
        or str(_dzen_file().get("session_id") or "")
    ).strip()


def dzen_csrf_token() -> str:
    return (
        settings.dzen_csrf_token
        or str(_section("dzen").get("csrf_token") or "")
        or str(_dzen_file().get("csrf_token") or "")
    ).strip()


def dzen_fp_token() -> str:
    return (
        settings.dzen_fp_token
        or str(_section("dzen").get("fp_token") or "")
        or str(_dzen_file().get("fp_token") or "")
    ).strip()


def dzen_cookies() -> dict[str, str]:
    cookies: dict[str, str] = {}
    stored = _dzen_file()
    raw_map = stored.get("cookies")
    if isinstance(raw_map, dict):
        for key, value in raw_map.items():
            if key and value is not None and str(value):
                cookies[str(key)] = str(value)
    for raw in (
        stored.get("cookie"),
        settings.dzen_cookie,
        str(_section("dzen").get("cookie") or ""),
    ):
        if raw:
            cookies.update(_parse_cookie_header(str(raw)))
    session_id = dzen_session_id()
    if session_id:
        cookies["Session_id"] = session_id
    dzen_sess = (settings.dzen_sess_id or str(_section("dzen").get("dzen_sess_id") or "")).strip()
    zen_sess = (settings.zen_session_id or str(_section("dzen").get("zen_session_id") or "")).strip()
    if dzen_sess:
        cookies["dzen_sess_id"] = dzen_sess
    if zen_sess:
        cookies["zen_session_id"] = zen_sess
    if "Session_id" not in cookies:
        fallback = cookies.get("dzen_sess_id") or ""
        if fallback.startswith("y0"):
            cookies["Session_id"] = fallback
    return {key: value for key, value in cookies.items() if value}


def dzen_channel_name() -> str:
    return (
        settings.dzen_channel_name or str(_section("dzen").get("channel_name") or "")
    ).strip().lstrip("@")


def platform_configured(platform: str) -> bool:
    platform = platform.lower()
    if platform == "youtube":
        return bool(youtube_client_id() and youtube_client_secret() and youtube_refresh_token())
    if platform == "vk":
        token, owner_id = vk_credentials()
        return bool(token and owner_id)
    if platform == "dzen":
        return bool(dzen_cookies())
    return False


def max_comment_length(platform: str) -> int:
    if platform == "dzen":
        return 2500
    if platform == "vk":
        return 4096
    return 10000
