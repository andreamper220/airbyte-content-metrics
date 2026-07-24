from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.airbyte_client import trigger_connection_syncs
from app.config import settings
from app.refresh_service import get_refresh_status, record_airbyte_sync, run_refresh_cycle

logger = logging.getLogger(__name__)


def _parse_connection_ids(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


async def _maybe_trigger_airbyte(last_airbyte_at: datetime | None) -> None:
    if not settings.airbyte_sync_enabled:
        return

    ids = _parse_connection_ids(settings.airbyte_connection_ids)
    if not settings.airbyte_api_url or not ids:
        logger.debug("Airbyte sync skipped: API URL or connection IDs not configured")
        return

    interval_sec = settings.airbyte_sync_interval_minutes * 60
    now = datetime.now(timezone.utc)
    if last_airbyte_at and (now - last_airbyte_at).total_seconds() < interval_sec:
        return

    results = await asyncio.to_thread(
        trigger_connection_syncs,
        api_base_url=settings.airbyte_api_url,
        connection_ids=ids,
        username=settings.airbyte_username,
        password=settings.airbyte_password,
    )
    ok = all(item.get("ok") for item in results) if results else False
    errors = "; ".join(
        f"{item['connection_id']}: {item.get('error', '?')}"
        for item in results
        if not item.get("ok")
    )
    record_airbyte_sync(ok=ok, error=errors or None)


async def auto_refresh_loop() -> None:
    if not settings.auto_refresh_enabled:
        logger.info("Auto-refresh disabled")
        return

    logger.info(
        "Auto-refresh enabled: marts every %s min, airbyte=%s",
        settings.mart_refresh_interval_minutes,
        settings.airbyte_sync_enabled,
    )

    await asyncio.sleep(settings.auto_refresh_startup_delay_seconds)

    while True:
        try:
            status = get_refresh_status()
            last_airbyte_raw = status.get("last_airbyte_sync_at")
            last_airbyte_at = None
            if last_airbyte_raw:
                last_airbyte_at = datetime.fromisoformat(last_airbyte_raw)

            await _maybe_trigger_airbyte(last_airbyte_at)

            await asyncio.to_thread(run_refresh_cycle, trigger="scheduler")
        except Exception:
            logger.exception("Scheduled refresh cycle failed")

        await asyncio.sleep(settings.mart_refresh_interval_minutes * 60)
