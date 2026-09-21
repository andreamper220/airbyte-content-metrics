import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from app.auth import is_auth_enabled, require_user, router as auth_router
from app.comments import (
    CommentError,
    commenting_for_video,
    commenting_status,
    ensure_comments_table,
    fetch_dzen_comments,
    post_comment,
)
from app.config import settings
from app.db import get_client, query
from app.refresh_service import get_refresh_status, run_refresh_cycle
from app.scheduler import auto_refresh_loop
from app.queries import (
    DAILY_TREND,
    METRIKA_STATUS,
    PLATFORM_CORRELATION,
    PLATFORM_SUMMARY,
    RECENT_COMMENTS,
    VIDEO_CLICKS,
    VIDEO_COMMENTS,
    VIDEO_COMMENTS_FALLBACK,
    VIDEO_DETAIL,
)
from app.dzen_meta import resolve_dzen_video
from app.dzen_stream import fetch_cdn, playlist_for_publication
from app.settings_store import PLATFORMS, ensure_default_utm_mapping, get_utm_mapping, save_utm_mapping
from app.video_embed import build_embed
from app.video_lookup import _video_id_candidates, load_video

logger = logging.getLogger(__name__)


def _jsonable_row(row: dict) -> dict:
    out = {}
    for key, value in row.items():
        out[key] = value.isoformat() if hasattr(value, "isoformat") else value
    return out


def _safe_query(sql: str, params: dict | None = None) -> list[dict]:
    try:
        return query(sql, params)
    except Exception:
        logger.exception("ClickHouse query failed")
        return []


def _load_video_comments(platform: str, video_id: str) -> list[dict]:
    video_ids = _video_id_candidates(platform, video_id) or [video_id]
    live: list[dict] = []
    if platform == "dzen":
        try:
            live = fetch_dzen_comments(video_id) or []
        except Exception:
            logger.exception("Failed to fetch Dzen comments")
    try:
        rows = query(VIDEO_COMMENTS, {"platform": platform, "video_ids": video_ids})
    except Exception:
        logger.exception("ClickHouse comments query failed, using fallback")
        rows = _safe_query(VIDEO_COMMENTS_FALLBACK, {"platform": platform, "video_ids": video_ids})
    out = []
    seen: set[str] = set()
    for row in rows:
        item = _jsonable_row(row)
        item["from_account"] = bool(item.get("from_account"))
        item["reply_to"] = item.get("reply_to") or ""
        item["comment_id"] = item.get("comment_id") or ""
        if item["comment_id"]:
            seen.add(item["comment_id"])
        out.append(item)
    for row in live:
        comment_id = str(row.get("comment_id") or "")
        if comment_id and comment_id in seen:
            continue
        published = row.get("published_at")
        out.append(
            {
                "comment_id": comment_id,
                "author": row.get("author") or "",
                "text": row.get("text") or "",
                "likes": int(row.get("likes") or 0),
                "published_at": published.isoformat() if hasattr(published, "isoformat") else published,
                "reply_to": row.get("reply_to") or "",
                "from_account": False,
            }
        )
    return out


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        ensure_comments_table()
    except Exception:
        logger.exception("Failed to ensure account_video_comments table")
    try:
        ensure_default_utm_mapping()
    except Exception:
        logger.exception("Failed to ensure default UTM mapping")
    refresh_task = asyncio.create_task(auto_refresh_loop())
    yield
    refresh_task.cancel()
    try:
        await refresh_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Content Analytics", version="0.2.0", lifespan=lifespan)

if is_auth_enabled():
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site="lax",
        https_only=settings.oauth_redirect_uri.startswith("https://"),
    )

app.include_router(auth_router)

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"


class UtmMappingRow(BaseModel):
    platform: str
    utm_source: str = Field(min_length=1)


class UtmMappingPayload(BaseModel):
    mappings: list[UtmMappingRow]


class VideoCommentPayload(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    reply_to: str = ""


api = APIRouter(prefix="/api", dependencies=[Depends(require_user)])


@api.get("/settings/utm-map")
async def api_get_utm_map():
    return {"mappings": get_utm_mapping(), "platforms": PLATFORMS}


@api.put("/settings/utm-map")
async def api_save_utm_map(payload: UtmMappingPayload):
    saved = save_utm_mapping([row.model_dump() for row in payload.mappings])
    return {"mappings": saved}


@api.get("/settings/commenting")
async def api_commenting_status():
    return {"platforms": commenting_status()}


@api.get("/refresh/status")
async def refresh_status():
    return {
        **get_refresh_status(),
        "auto_refresh_enabled": settings.auto_refresh_enabled,
        "mart_refresh_interval_minutes": settings.mart_refresh_interval_minutes,
        "airbyte_sync_enabled": settings.airbyte_sync_enabled,
        "airbyte_sync_interval_minutes": settings.airbyte_sync_interval_minutes,
    }


@api.post("/refresh")
async def refresh_marts():
    return await asyncio.to_thread(run_refresh_cycle, trigger="manual")


@api.get("/viral")
async def viral_videos(days: int = 30):
    return []


@api.get("/comments/recent")
async def recent_comments(days: int = 30, limit: int = 50):
    days = max(1, min(days, 90))
    limit = max(1, min(limit, 100))
    rows = _safe_query(RECENT_COMMENTS, {"days": days, "limit": limit})
    return {"comments": [_jsonable_row(row) for row in rows]}


@api.get("/video/{platform}/{video_id}")
async def video_detail(platform: str, video_id: str):
    loaded = load_video(platform, video_id)
    if not loaded:
        raise HTTPException(status_code=404, detail="Video not found")
    video, video_id = loaded
    video = _jsonable_row(video)
    comments = _load_video_comments(platform, video_id)
    click_rows = _safe_query(VIDEO_CLICKS, {"platform": platform, "video_id": video_id})
    clicks = _jsonable_row(click_rows[0]) if click_rows else {}
    unique = int(clicks.get("unique_clicks") or 0)
    per_video = platform == "vk"
    mode = "per_video" if per_video else (clicks.get("mode") or "weekly_bio")
    week_start = str(clicks.get("week_start") or "") if mode == "weekly_bio" else ""
    week_end = str(clicks.get("week_end") or "") if mode == "weekly_bio" else ""
    if week_start.startswith("1970"):
        week_start = ""
        week_end = ""
    embed = build_embed(platform, video_id, video.get("url") or "")
    if platform == "dzen" and video.get("hls"):
        embed = {
            "type": "hls",
            "src": f"/api/dzen/hls/{video_id}",
            "poster": video.get("image") or "",
            "url": video.get("url") or "",
        }
    elif embed.get("type") == "link" and video.get("image"):
        embed["image"] = video["image"]
    return {
        "video": video,
        "description": video.get("title") or "",
        "embed": embed,
        "comments": comments,
        "commenting": commenting_for_video(platform),
        "clicks": {
            "mode": mode,
            "utm_content": clicks.get("utm_content") or (f"video_{video_id}" if per_video else ""),
            "week_start": week_start,
            "week_end": week_end,
            "unique_clicks": unique,
            "sessions": int(clicks.get("sessions") or 0),
            "amount_rub": unique * 20 if mode == "weekly_bio" else None,
        },
    }


@api.post("/video/{platform}/{video_id}/comments")
async def api_post_video_comment(
    platform: str,
    video_id: str,
    payload: VideoCommentPayload,
    user: str = Depends(require_user),
):
    loaded = load_video(platform, video_id)
    if not loaded:
        raise HTTPException(status_code=404, detail="Video not found")
    _video, resolved_id = loaded
    try:
        comment = await asyncio.to_thread(
            post_comment,
            platform,
            resolved_id,
            payload.text,
            reply_to=payload.reply_to,
            posted_by=user,
        )
    except CommentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {
        "comment": {
            "comment_id": comment.comment_id,
            "author": comment.author,
            "text": comment.text,
            "likes": comment.likes,
            "published_at": comment.published_at.isoformat() if comment.published_at else None,
            "reply_to": comment.reply_to,
            "from_account": True,
        }
    }


@api.get("/dzen/hls/{video_id}")
async def dzen_hls(video_id: str):
    return playlist_for_publication(video_id)


@api.get("/dzen/cdn")
async def dzen_cdn(u: str):
    return fetch_cdn(u)


@api.get("/correlation")
async def correlation(days: int = 30):
    rows = query(PLATFORM_CORRELATION, {"days": days})
    if not settings.dzen_channel_name:
        return rows
    out = []
    for row in rows:
        item = dict(row)
        if item.get("platform") == "dzen" and item.get("top_video_id") and (
            not item.get("top_video_title")
            or str(item.get("top_video_title", "")).strip().lower() in {"ролики", "shorts", "видео", "ролик"}
        ):
            resolved = resolve_dzen_video(
                str(item.get("top_video_id") or ""),
                None,
                str(item.get("top_video_title") or ""),
                settings.dzen_channel_name,
                fallback=False,
            )
            if resolved:
                item["top_video_title"] = resolved.get("title") or item.get("top_video_title")
                item["top_video_id"] = resolved.get("video_id") or item.get("top_video_id")
        out.append(item)
    return out


@api.get("/summary")
async def summary(days: int = 30):
    return query(PLATFORM_SUMMARY, {"days": days})


@api.get("/trend")
async def trend(days: int = 30):
    return query(DAILY_TREND, {"days": days})


@api.get("/web/metrika-status")
async def web_metrika_status(days: int = 30):
    try:
        rows = query(METRIKA_STATUS, {"days": days})
        row = rows[0] if rows else {}
        return {
            "raw_sessions": int(row.get("raw_sessions") or 0),
            "utm_sessions": int(row.get("utm_sessions") or 0),
            "utm_sessions_period": int(row.get("utm_sessions_period") or 0),
            "last_extracted_at": row.get("last_extracted_at"),
        }
    except Exception as exc:
        return {
            "raw_sessions": 0,
            "utm_sessions": 0,
            "utm_sessions_period": 0,
            "last_extracted_at": None,
            "error": str(exc),
        }


app.include_router(api)


@app.get("/health")
async def health():
    try:
        get_client().command("SELECT 1")
        return {"status": "ok"}
    except Exception as exc:
        return JSONResponse({"status": "error", "detail": str(exc)}, status_code=503)


def _serve_frontend_index() -> FileResponse:
    if not FRONTEND_INDEX.is_file():
        raise HTTPException(
            status_code=503,
            detail="Frontend build not found. Run `npm run build` in content-analytics/frontend.",
        )
    return FileResponse(FRONTEND_INDEX)


@app.get("/")
async def dashboard():
    return _serve_frontend_index()


@app.get("/settings")
async def settings_page():
    return _serve_frontend_index()


@app.get("/login")
async def login_page():
    return _serve_frontend_index()


if FRONTEND_DIST.is_dir():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        file_path = FRONTEND_DIST / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return _serve_frontend_index()


def run():
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)
