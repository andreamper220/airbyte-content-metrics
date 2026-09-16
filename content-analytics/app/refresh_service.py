from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from app.db import get_client
from app.queries import REFRESH_MART_VIDEOS, REFRESH_PLATFORM_DAILY, REFRESH_WEB_TRAFFIC

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_state: dict[str, Any] = {
    "in_progress": False,
    "last_refresh_at": None,
    "last_refresh_ok": None,
    "last_error": None,
    "last_airbyte_sync_at": None,
    "last_airbyte_sync_ok": None,
    "last_airbyte_error": None,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def refresh_marts() -> None:
    client = get_client()
    client.command("TRUNCATE TABLE analytics.mart_web_traffic_daily")
    client.command("TRUNCATE TABLE analytics.mart_platform_daily")
    for sql in (REFRESH_MART_VIDEOS, REFRESH_WEB_TRAFFIC, REFRESH_PLATFORM_DAILY):
        client.command(sql)


def run_refresh_cycle(*, trigger: str = "manual") -> dict[str, Any]:
    with _lock:
        if _state["in_progress"]:
            return get_refresh_status()
        _state["in_progress"] = True

    started = _utc_now()
    try:
        refresh_marts()
        finished = _utc_now()
        with _lock:
            _state["last_refresh_at"] = finished
            _state["last_refresh_ok"] = True
            _state["last_error"] = None
        logger.info("Mart refresh completed (%s) in %.1fs", trigger, (finished - started).total_seconds())
    except Exception as exc:
        with _lock:
            _state["last_refresh_at"] = _utc_now()
            _state["last_refresh_ok"] = False
            _state["last_error"] = str(exc)
        logger.exception("Mart refresh failed (%s)", trigger)
        raise
    finally:
        with _lock:
            _state["in_progress"] = False

    return get_refresh_status()


def record_airbyte_sync(*, ok: bool, error: str | None = None) -> None:
    with _lock:
        _state["last_airbyte_sync_at"] = _utc_now()
        _state["last_airbyte_sync_ok"] = ok
        _state["last_airbyte_error"] = error


def get_refresh_status() -> dict[str, Any]:
    with _lock:
        return {
            "in_progress": _state["in_progress"],
            "last_refresh_at": _iso(_state["last_refresh_at"]),
            "last_refresh_ok": _state["last_refresh_ok"],
            "last_error": _state["last_error"],
            "last_airbyte_sync_at": _iso(_state["last_airbyte_sync_at"]),
            "last_airbyte_sync_ok": _state["last_airbyte_sync_ok"],
            "last_airbyte_error": _state["last_airbyte_error"],
        }
