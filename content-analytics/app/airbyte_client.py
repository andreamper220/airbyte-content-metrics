from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


def trigger_connection_syncs(
    *,
    api_base_url: str,
    connection_ids: list[str],
    username: str = "",
    password: str = "",
) -> list[dict[str, Any]]:
    """Fire-and-forget Airbyte sync jobs for each connection id."""
    if not api_base_url or not connection_ids:
        return []

    base = api_base_url.rstrip("/")
    if not base.endswith("/api/v1"):
        base = f"{base}/api/v1"

    results: list[dict[str, Any]] = []
    for connection_id in connection_ids:
        payload = json.dumps({"connectionId": connection_id}).encode("utf-8")
        request = urllib.request.Request(
            f"{base}/connections/sync",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if username:
            import base64

            token = base64.b64encode(f"{username}:{password}".encode()).decode()
            request.add_header("Authorization", f"Basic {token}")

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode())
            results.append({"connection_id": connection_id, "ok": True, "job": body})
            logger.info("Airbyte sync triggered for connection %s", connection_id)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            results.append({"connection_id": connection_id, "ok": False, "error": detail or str(exc)})
            logger.warning("Airbyte sync failed for %s: %s", connection_id, detail or exc)
        except Exception as exc:
            results.append({"connection_id": connection_id, "ok": False, "error": str(exc)})
            logger.warning("Airbyte sync failed for %s: %s", connection_id, exc)

    return results
