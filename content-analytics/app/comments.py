from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx

from app import comment_credentials as creds
from app.config import settings
from app.db import get_client
from app.dzen_meta import normalize_publication_id

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_CSRF_RE = re.compile(
    r'(?:csrf[_-]?token|_csrf)["\'\\s:=]+["\']([A-Za-z0-9._/=+-]{8,})',
    re.IGNORECASE,
)

_youtube_token: tuple[str, float] | None = None
_youtube_channel: tuple[str, str] | None = None  # id, title
_vk_identity: tuple[str, str] | None = None  # id, title


class CommentError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class PostedComment:
    platform: str
    video_id: str
    comment_id: str
    author: str
    text: str
    likes: int = 0
    published_at: datetime | None = None
    reply_to: str = ""
    from_account: bool = True


def ensure_comments_table() -> None:
    client = get_client()
    client.command(
        """
        CREATE TABLE IF NOT EXISTS analytics.account_video_comments
        (
            platform LowCardinality(String),
            video_id String,
            comment_id String,
            author String,
            text String,
            likes UInt32,
            published_at DateTime,
            reply_to String,
            posted_by String,
            _airbyte_extracted_at DateTime64(3) DEFAULT now()
        )
        ENGINE = ReplacingMergeTree(_airbyte_extracted_at)
        ORDER BY (platform, video_id, comment_id)
        """
    )
    client.command(
        """
        CREATE TABLE IF NOT EXISTS analytics.platform_video_comments
        (
            platform LowCardinality(String),
            video_id String,
            comment_id String,
            author String,
            text String,
            likes UInt32,
            published_at DateTime,
            _airbyte_extracted_at DateTime64(3) DEFAULT now()
        )
        ENGINE = ReplacingMergeTree(_airbyte_extracted_at)
        ORDER BY (platform, video_id, comment_id)
        """
    )


def save_posted_comment(comment: PostedComment, posted_by: str) -> None:
    try:
        ensure_comments_table()
        published = comment.published_at or datetime.now(timezone.utc).replace(tzinfo=None)
        get_client().insert(
            "account_video_comments",
            [
                [
                    comment.platform,
                    comment.video_id,
                    comment.comment_id,
                    comment.author,
                    comment.text,
                    int(comment.likes or 0),
                    published,
                    comment.reply_to or "",
                    posted_by or "",
                ]
            ],
            column_names=[
                "platform",
                "video_id",
                "comment_id",
                "author",
                "text",
                "likes",
                "published_at",
                "reply_to",
                "posted_by",
            ],
        )
    except Exception:
        logger.exception("Failed to persist posted comment")


def save_platform_comments(platform: str, video_id: str, comments: list[dict[str, Any]]) -> None:
    if not comments:
        return
    try:
        ensure_comments_table()
        rows = []
        for item in comments:
            comment_id = str(item.get("comment_id") or "").strip()
            text = str(item.get("text") or "").strip()
            if not comment_id or not text:
                continue
            published = item.get("published_at")
            if not isinstance(published, datetime):
                published = _parse_iso(published) or _utc_now()
            if published.tzinfo:
                published = published.astimezone(timezone.utc).replace(tzinfo=None)
            rows.append(
                [
                    platform,
                    video_id,
                    comment_id,
                    str(item.get("author") or ""),
                    text,
                    int(item.get("likes") or 0),
                    published,
                ]
            )
        if not rows:
            return
        get_client().insert(
            "platform_video_comments",
            rows,
            column_names=["platform", "video_id", "comment_id", "author", "text", "likes", "published_at"],
        )
    except Exception:
        logger.exception("Failed to persist %s comments", platform)


def commenting_status() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for platform in creds.COMMENTABLE_PLATFORMS:
        enabled = creds.platform_configured(platform)
        identity = ""
        if enabled:
            try:
                identity = account_label(platform)
            except Exception:
                logger.exception("Failed to resolve %s comment identity", platform)
                identity = _fallback_label(platform)
        out[platform] = {
            "enabled": enabled,
            "as": identity or None,
            "max_length": creds.max_comment_length(platform),
        }
    return out


def commenting_for_video(platform: str) -> dict[str, Any]:
    platform = platform.lower()
    if platform not in creds.COMMENTABLE_PLATFORMS:
        return {"enabled": False, "as": None, "max_length": 0, "supported": False}
    enabled = creds.platform_configured(platform)
    identity = ""
    if enabled:
        try:
            identity = account_label(platform)
        except Exception:
            logger.exception("Failed to resolve %s comment identity", platform)
            identity = _fallback_label(platform)
    return {
        "enabled": enabled,
        "as": identity or None,
        "max_length": creds.max_comment_length(platform),
        "supported": True,
    }


def account_label(platform: str) -> str:
    platform = platform.lower()
    if platform == "youtube":
        _, title = _youtube_channel_identity()
        return title
    if platform == "vk":
        _, title = _vk_account_identity()
        return title
    if platform == "dzen":
        return creds.dzen_channel_name() or "канал Дзена"
    return platform


def _fallback_label(platform: str) -> str:
    if platform == "youtube":
        return creds.youtube_channel_id() or "канал YouTube"
    if platform == "vk":
        _, owner_id = creds.vk_credentials()
        return f"VK {owner_id}" if owner_id else "аккаунт VK"
    if platform == "dzen":
        return creds.dzen_channel_name() or "канал Дзена"
    return platform


def post_comment(
    platform: str,
    video_id: str,
    text: str,
    *,
    reply_to: str = "",
    posted_by: str = "",
) -> PostedComment:
    platform = platform.lower()
    video_id = (video_id or "").strip()
    text = (text or "").strip()
    reply_to = (reply_to or "").strip()
    if platform not in creds.COMMENTABLE_PLATFORMS:
        raise CommentError("Комментарии с дашборда доступны для YouTube, VK и Дзена")
    if not video_id:
        raise CommentError("Не указан ролик")
    if not text:
        raise CommentError("Введите текст комментария")
    limit = creds.max_comment_length(platform)
    if len(text) > limit:
        raise CommentError(f"Слишком длинный комментарий (макс. {limit} символов)")
    if not creds.platform_configured(platform):
        raise CommentError(
            "Не настроены токены аккаунта для этой площадки. Добавьте их в .env и перезапустите приложение.",
            status_code=503,
        )

    if platform == "youtube":
        comment = _post_youtube(video_id, text, reply_to)
    elif platform == "vk":
        comment = _post_vk(video_id, text, reply_to)
    else:
        comment = _post_dzen(video_id, text, reply_to)

    save_posted_comment(comment, posted_by)
    return comment


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _youtube_access_token() -> str:
    global _youtube_token
    now = datetime.now(timezone.utc).timestamp()
    if _youtube_token and _youtube_token[1] - 60 > now:
        return _youtube_token[0]
    client_id = creds.youtube_client_id()
    client_secret = creds.youtube_client_secret()
    refresh_token = creds.youtube_refresh_token()
    if not (client_id and client_secret and refresh_token):
        raise CommentError("Не задан YouTube refresh token", status_code=503)
    response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    payload = _json_body(response)
    token = str(payload.get("access_token") or "")
    if not token:
        raise CommentError(_google_error(payload) or "Не удалось обновить токен YouTube", status_code=502)
    expires = now + int(payload.get("expires_in") or 3500)
    _youtube_token = (token, expires)
    return token


def _youtube_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_youtube_access_token()}", "Accept": "application/json"}


def _youtube_channel_identity() -> tuple[str, str]:
    global _youtube_channel
    if _youtube_channel:
        return _youtube_channel
    configured = creds.youtube_channel_id()
    params: dict[str, str] = {"part": "snippet", "maxResults": "1"}
    if configured:
        params["id"] = configured
    else:
        params["mine"] = "true"
    response = httpx.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params=params,
        headers=_youtube_headers(),
        timeout=30,
    )
    payload = _json_body(response)
    items = payload.get("items") or []
    if not items:
        raise CommentError("Не найден YouTube-канал для этого токена", status_code=502)
    item = items[0]
    channel_id = str(item.get("id") or configured)
    title = str((item.get("snippet") or {}).get("title") or "канал YouTube")
    _youtube_channel = (channel_id, title)
    return _youtube_channel


def _youtube_video_channel_id(video_id: str) -> str:
    configured = creds.youtube_channel_id()
    if configured:
        return configured
    response = httpx.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "snippet", "id": video_id},
        headers=_youtube_headers(),
        timeout=30,
    )
    payload = _json_body(response)
    items = payload.get("items") or []
    if items:
        return str((items[0].get("snippet") or {}).get("channelId") or "")
    channel_id, _ = _youtube_channel_identity()
    return channel_id


def _post_youtube(video_id: str, text: str, reply_to: str) -> PostedComment:
    channel_id, author = _youtube_channel_identity()
    if reply_to:
        body = {"snippet": {"parentId": reply_to, "textOriginal": text}}
        response = httpx.post(
            "https://www.googleapis.com/youtube/v3/comments",
            params={"part": "snippet"},
            headers=_youtube_headers(),
            json=body,
            timeout=30,
        )
        payload = _json_body(response)
        if response.status_code >= 400:
            raise CommentError(_google_error(payload) or "YouTube отклонил ответ на комментарий", status_code=502)
        snippet = payload.get("snippet") or {}
        return PostedComment(
            platform="youtube",
            video_id=video_id,
            comment_id=str(payload.get("id") or f"yt-{uuid4().hex[:12]}"),
            author=str(snippet.get("authorDisplayName") or author),
            text=str(snippet.get("textDisplay") or snippet.get("textOriginal") or text),
            published_at=_parse_iso(snippet.get("publishedAt")) or _utc_now(),
            reply_to=reply_to,
        )

    video_channel = _youtube_video_channel_id(video_id) or channel_id
    body = {
        "snippet": {
            "channelId": video_channel,
            "videoId": video_id,
            "topLevelComment": {"snippet": {"textOriginal": text}},
        }
    }
    response = httpx.post(
        "https://www.googleapis.com/youtube/v3/commentThreads",
        params={"part": "snippet"},
        headers=_youtube_headers(),
        json=body,
        timeout=30,
    )
    payload = _json_body(response)
    if response.status_code >= 400:
        raise CommentError(_google_error(payload) or "YouTube отклонил комментарий", status_code=502)
    top = ((payload.get("snippet") or {}).get("topLevelComment") or {})
    snippet = top.get("snippet") or {}
    comment_id = str(top.get("id") or payload.get("id") or f"yt-{uuid4().hex[:12]}")
    return PostedComment(
        platform="youtube",
        video_id=video_id,
        comment_id=comment_id,
        author=str(snippet.get("authorDisplayName") or author),
        text=str(snippet.get("textDisplay") or snippet.get("textOriginal") or text),
        published_at=_parse_iso(snippet.get("publishedAt")) or _utc_now(),
    )


def _split_vk_video_id(video_id: str, default_owner: int) -> tuple[int, int]:
    raw = video_id.strip()
    if "_" in raw:
        owner_part, numeric_part = raw.split("_", 1)
        try:
            return int(owner_part), int(re.sub(r"\D", "", numeric_part) or "0")
        except ValueError as exc:
            raise CommentError("Некорректный ID видео VK") from exc
    try:
        return default_owner, int(raw)
    except ValueError as exc:
        raise CommentError("Некорректный ID видео VK") from exc


def _vk_api(method: str, params: dict[str, Any]) -> dict[str, Any]:
    token, _owner_id = creds.vk_credentials()
    payload = {
        **params,
        "access_token": token,
        "v": settings.vk_api_version or "5.199",
    }
    response = httpx.post(f"https://api.vk.com/method/{method}", data=payload, timeout=30)
    body = _json_body(response)
    error = body.get("error")
    if error:
        message = str(error.get("error_msg") or "ошибка VK API")
        code = error.get("error_code")
        raise CommentError(f"VK API ({code}): {message}", status_code=502)
    return body.get("response") if "response" in body else body


def _vk_account_identity() -> tuple[str, str]:
    global _vk_identity
    if _vk_identity:
        return _vk_identity
    token, owner_id = creds.vk_credentials()
    if owner_id < 0:
        group_id = abs(owner_id)
        data = _vk_api("groups.getById", {"group_id": group_id, "group_ids": str(group_id)})
        items = data if isinstance(data, list) else (data.get("groups") if isinstance(data, dict) else [])
        item = items[0] if items else {}
        title = str(item.get("name") or f"сообщество {group_id}")
        identity = (str(owner_id), title)
    else:
        data = _vk_api("users.get", {"user_ids": owner_id})
        item = data[0] if isinstance(data, list) and data else {}
        title = " ".join(part for part in (item.get("first_name"), item.get("last_name")) if part).strip()
        identity = (str(owner_id), title or f"VK {owner_id}")
    _vk_identity = identity
    return identity


def _post_vk(video_id: str, text: str, reply_to: str) -> PostedComment:
    _, owner_id = creds.vk_credentials()
    owner, numeric_id = _split_vk_video_id(video_id, owner_id)
    if not numeric_id:
        raise CommentError("Некорректный ID видео VK")
    _, author = _vk_account_identity()
    params: dict[str, Any] = {
        "owner_id": owner,
        "video_id": numeric_id,
        "message": text,
    }
    if owner < 0 and settings.vk_comment_from_group:
        params["from_group"] = 1
    if reply_to:
        try:
            params["reply_to_comment"] = int(reply_to)
        except ValueError:
            raise CommentError("Некорректный ID комментария для ответа")
    try:
        comment_id = _vk_api("video.createComment", params)
    except CommentError:
        if not params.get("from_group"):
            raise
        params = {key: value for key, value in params.items() if key != "from_group"}
        comment_id = _vk_api("video.createComment", params)
    if isinstance(comment_id, dict):
        comment_id = comment_id.get("comment_id") or comment_id.get("id")
    return PostedComment(
        platform="vk",
        video_id=f"{owner}_{numeric_id}",
        comment_id=str(comment_id or f"vk-{uuid4().hex[:12]}"),
        author=author,
        text=text,
        published_at=_utc_now(),
        reply_to=reply_to,
    )


def _dzen_document_id(video_id: str) -> str:
    pid = normalize_publication_id(video_id)
    if video_id.startswith("gif:"):
        return video_id
    return f"gif:{pid}" if pid else video_id


def _extract_csrf(client: httpx.Client, html: str) -> str:
    for cookie_name in ("csrf_token", "_csrf", "yandex_csrf"):
        value = client.cookies.get(cookie_name)
        if value:
            return str(value)
    match = _CSRF_RE.search(html or "")
    return match.group(1) if match else ""


def _dzen_client(video_id: str) -> tuple[httpx.Client, str, str]:
    session_id = creds.dzen_session_id()
    csrf = creds.dzen_csrf_token()
    pid = normalize_publication_id(video_id)
    referer = f"https://dzen.ru/shorts/{pid}" if pid else "https://dzen.ru/"
    client = httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://dzen.ru",
            "Referer": referer,
        },
        cookies={"Session_id": session_id},
    )
    if not csrf:
        try:
            page = client.get(referer)
            csrf = _extract_csrf(client, page.text)
        except httpx.HTTPError:
            logger.exception("Failed to fetch Dzen CSRF token")
    if csrf:
        client.headers["x-csrf-token"] = csrf
        client.headers["X-Csrf-Token"] = csrf
    return client, csrf, _dzen_document_id(video_id)


def fetch_dzen_comments(video_id: str) -> list[dict[str, Any]]:
    from app.dzen_meta import dzen_comment_meta

    pid = normalize_publication_id(video_id)
    channel = creds.dzen_channel_name() or settings.dzen_channel_name
    meta = dzen_comment_meta(video_id, channel or None) or {}
    document_id = str(meta.get("document_id") or _dzen_document_id(video_id))
    token = str(meta.get("token") or "")
    publisher_id = str(meta.get("publisher_id") or "")
    session_id = creds.dzen_session_id()
    csrf = creds.dzen_csrf_token()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://dzen.ru",
        "Referer": f"https://dzen.ru/shorts/{pid}" if pid else "https://dzen.ru/",
    }
    if csrf:
        headers["x-csrf-token"] = csrf
        headers["X-Csrf-Token"] = csrf
    cookies = {"Session_id": session_id} if session_id else {}
    found: list[dict[str, Any]] = []
    attempts: list[tuple[str, dict[str, Any] | None]] = [
        ("https://dzen.ru/api/comments", {"documentId": document_id, "commentsToken": token, "limit": "30"}),
        ("https://dzen.ru/api/v3/comments", {"documentId": document_id, "commentsToken": token, "limit": "30"}),
        ("https://dzen.ru/api/v3/launcher/comments", {"documentId": document_id, "comments_token": token}),
        ("https://dzen.ru/api/comments/get-root-comments", {"entityId": document_id, "documentId": document_id}),
    ]
    if publisher_id:
        attempts.append(
            (f"https://dzen.ru/editor-api/v2/comments?publisherId={publisher_id}", {"documentId": document_id})
        )
    with httpx.Client(timeout=8, follow_redirects=True, headers=headers, cookies=cookies) as client:
        for url, params in attempts:
            try:
                response = client.get(url, params={k: v for k, v in (params or {}).items() if v})
            except httpx.HTTPError:
                continue
            parsed = _comments_from_payload(_json_body(response), pid or video_id)
            if parsed:
                found = parsed
                break
        if not found:
            try:
                response = client.post(
                    "https://dzen.ru/api/comments",
                    json={"documentId": document_id, "commentsToken": token, "limit": 30},
                )
                found = _comments_from_payload(_json_body(response), pid or video_id)
            except httpx.HTTPError:
                found = []
    if found:
        save_platform_comments("dzen", pid or video_id, found)
    return found


def _comments_from_payload(payload: Any, video_id: str) -> list[dict[str, Any]]:
    authors: dict[str, str] = {}
    if isinstance(payload, dict):
        raw_authors = payload.get("authors") or payload.get("users") or {}
        if isinstance(raw_authors, dict):
            for key, value in raw_authors.items():
                if isinstance(value, dict):
                    name = str(value.get("name") or value.get("displayName") or "")
                    if name:
                        authors[str(key)] = name
                elif isinstance(value, str) and value.strip():
                    authors[str(key)] = value.strip()
        elif isinstance(raw_authors, list):
            for value in raw_authors:
                if not isinstance(value, dict):
                    continue
                uid = str(value.get("uid") or value.get("id") or "")
                name = str(value.get("name") or value.get("displayName") or "")
                if uid and name:
                    authors[uid] = name

    items: list[Any] = []
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        if payload.get("error") or payload.get("errtext") or payload.get("errors"):
            return []
        for key in ("comments", "items", "result", "data", "entries"):
            value = payload.get(key)
            if isinstance(value, list):
                items = value
                break
            if isinstance(value, dict):
                nested = value.get("comments") or value.get("items")
                if isinstance(nested, list):
                    items = nested
                    break

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        text = str(
            item.get("text")
            or item.get("message")
            or item.get("content")
            or item.get("body")
            or ""
        ).strip()
        if not text:
            continue
        comment_id = _comment_id_from_payload(item) or f"dzen-{uuid4().hex[:12]}"
        if comment_id in seen:
            continue
        seen.add(comment_id)
        author_id = str(item.get("authorId") or item.get("author_id") or item.get("uid") or "")
        author = _author_from_payload(item, authors.get(author_id) or "Пользователь Дзена")
        likes = item.get("likes") or item.get("likeCount") or item.get("likesCount") or 0
        try:
            likes_n = int(likes)
        except (TypeError, ValueError):
            likes_n = _first_int(likes)
        published = (
            item.get("publishedAt")
            or item.get("published_at")
            or item.get("createTime")
            or item.get("createdAt")
            or item.get("date")
        )
        out.append(
            {
                "comment_id": comment_id,
                "author": author,
                "text": text,
                "likes": likes_n,
                "published_at": published,
                "reply_to": str(item.get("parentId") or item.get("parentCommentId") or ""),
            }
        )
    return out


def _first_int(value: Any) -> int:
    if isinstance(value, dict):
        for key in ("count", "value", "total"):
            try:
                return int(value.get(key) or 0)
            except (TypeError, ValueError):
                continue
    return 0


def _comment_id_from_payload(payload: Any) -> str:
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    if isinstance(payload, (int, float)):
        return str(int(payload))
    if not isinstance(payload, dict):
        return ""
    for key in ("id", "commentId", "comment_id", "entityId"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    comment = payload.get("comment") or payload.get("item") or payload.get("result") or payload.get("data")
    if isinstance(comment, dict):
        nested = _comment_id_from_payload(comment)
        if nested:
            return nested
    items = payload.get("items") or payload.get("comments")
    if isinstance(items, list) and items:
        nested = _comment_id_from_payload(items[0])
        if nested:
            return nested
    return ""


def _author_from_payload(payload: Any, fallback: str) -> str:
    if not isinstance(payload, dict):
        return fallback
    for key in ("authorName", "name", "displayName"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key in ("author", "user", "publisher", "comment"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            name = _author_from_payload(nested, "")
            if name:
                return name
        if isinstance(nested, str) and nested.strip() and key == "author":
            return nested.strip()
    return fallback


def _post_dzen(video_id: str, text: str, reply_to: str) -> PostedComment:
    author = creds.dzen_channel_name() or "канал Дзена"
    client, _csrf, document_id = _dzen_client(video_id)
    pid = normalize_publication_id(video_id)
    payloads: list[dict[str, Any]] = [
        {"documentId": document_id, "text": text},
        {"documentId": document_id, "message": text},
        {"documentId": document_id, "comment": {"text": text}},
        {"publicationId": document_id, "text": text},
        {"objectId": document_id, "text": text},
        {"entityId": document_id, "text": text},
    ]
    if reply_to:
        for item in payloads:
            item["parentCommentId"] = reply_to
            item["parentId"] = reply_to
    endpoints = (
        "https://dzen.ru/api/comments",
        "https://dzen.ru/api/v3/comments",
        "https://dzen.ru/api/v3/launcher/comments",
        "https://dzen.ru/api/comments/create",
        "https://dzen.ru/api/v3/comments/create",
    )
    last_error = "Дзен отклонил комментарий"
    try:
        for url in endpoints:
            for body in payloads:
                try:
                    response = client.post(url, json=body)
                except httpx.HTTPError as exc:
                    last_error = str(exc)
                    continue
                payload = _json_body(response)
                if response.status_code >= 400:
                    last_error = _dzen_error(payload, response.status_code)
                    continue
                comment_id = _comment_id_from_payload(payload) or f"dzen-{uuid4().hex[:12]}"
                return PostedComment(
                    platform="dzen",
                    video_id=pid or video_id,
                    comment_id=comment_id,
                    author=_author_from_payload(payload, author),
                    text=text,
                    published_at=_utc_now(),
                    reply_to=reply_to,
                )
    finally:
        client.close()
    raise CommentError(last_error, status_code=502)


def _json_body(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        text = (response.text or "").strip()
        return {"error": text[:400]} if text else {}
    return payload if isinstance(payload, dict) else {"result": payload}


def _google_error(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        message = str(error.get("message") or "")
        errors = error.get("errors") or []
        reason = ""
        if errors and isinstance(errors[0], dict):
            reason = str(errors[0].get("reason") or "")
        if reason == "commentsDisabled":
            return "Комментарии к этому ролику YouTube отключены"
        if reason == "ineligibleAccount":
            return "Этот Google-аккаунт нельзя использовать для комментариев YouTube"
        if reason == "forbidden":
            return "Недостаточно прав YouTube. Нужен OAuth со scope youtube.force-ssl"
        return message or reason
    if isinstance(error, str):
        description = str(payload.get("error_description") or "")
        return f"{error}: {description}".strip(": ")
    return ""


def _dzen_error(payload: dict[str, Any], status_code: int) -> str:
    for key in ("message", "error", "error_message", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = value.get("message") or value.get("title")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    if status_code in {401, 403}:
        return "Сессия Дзена недействительна. Обновите DZEN_SESSION_ID и CSRF-токен"
    return f"Дзен вернул HTTP {status_code}"


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    raw = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed
