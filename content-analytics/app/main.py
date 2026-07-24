from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.db import get_client, query
from app.queries import (
    DAILY_TREND,
    PLATFORM_CORRELATION,
    PLATFORM_SUMMARY,
    REFRESH_MART_VIDEOS,
    REFRESH_PLATFORM_DAILY,
    REFRESH_WEB_TRAFFIC,
    TOP_VIRAL,
    VIDEO_COMMENTS,
    VIDEO_DETAIL,
)
from app.settings_store import PLATFORMS, get_utm_mapping, save_utm_mapping
from app.video_embed import build_embed

app = FastAPI(title="Content Analytics", version="0.2.0")

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"


class UtmMappingRow(BaseModel):
    platform: str
    utm_source: str = Field(min_length=1)


class UtmMappingPayload(BaseModel):
    mappings: list[UtmMappingRow]


@app.get("/api/settings/utm-map")
async def api_get_utm_map():
    return {"mappings": get_utm_mapping(), "platforms": PLATFORMS}


@app.put("/api/settings/utm-map")
async def api_save_utm_map(payload: UtmMappingPayload):
    saved = save_utm_mapping([row.model_dump() for row in payload.mappings])
    return {"mappings": saved}


@app.post("/api/refresh")
async def refresh_marts():
    client = get_client()
    for sql in (REFRESH_MART_VIDEOS, REFRESH_WEB_TRAFFIC, REFRESH_PLATFORM_DAILY):
        client.command(sql)
    return {"status": "ok"}


@app.get("/api/viral")
async def viral_videos(days: int = 30):
    return query(TOP_VIRAL, {"days": days})


@app.get("/api/video/{platform}/{video_id}")
async def video_detail(platform: str, video_id: str):
    rows = query(VIDEO_DETAIL, {"platform": platform, "video_id": video_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Video not found")
    video = rows[0]
    comments = query(VIDEO_COMMENTS, {"platform": platform, "video_id": video_id})
    return {
        "video": video,
        "description": video.get("title") or "",
        "embed": build_embed(platform, video_id, video.get("url") or ""),
        "comments": comments,
    }


@app.get("/api/correlation")
async def correlation(days: int = 30):
    return query(PLATFORM_CORRELATION, {"days": days})


@app.get("/api/summary")
async def summary(days: int = 30):
    return query(PLATFORM_SUMMARY, {"days": days})


@app.get("/api/trend")
async def trend(days: int = 30):
    return query(DAILY_TREND, {"days": days})


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
