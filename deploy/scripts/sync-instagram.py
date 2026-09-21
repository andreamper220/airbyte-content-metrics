#!/usr/bin/env python3
"""Pull Instagram media + insights into ClickHouse using a long-lived user token."""
from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

GRAPH = "https://graph.facebook.com/v21.0"
SECRET = Path("/var/www/content/deploy/secrets/source-instagram-config.json")
CH = ["docker", "exec", "-i", "content-metrics-clickhouse-1", "clickhouse-client"]


def load_cfg() -> dict:
    cfg = json.loads(SECRET.read_text())
    if not cfg.get("access_token") or not cfg.get("business_account_id"):
        raise SystemExit("source-instagram-config.json needs access_token and business_account_id")
    return cfg


def graph(token: str, path: str, extra: dict | None = None) -> dict:
    query = {"access_token": token}
    if extra:
        query.update(extra)
    url = f"{GRAPH}/{path}?{urllib.parse.urlencode(query)}"
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"{path} {exc.code}: {body[:500]}") from exc


def all_media(token: str, ig_id: str) -> list[dict]:
    rows: list[dict] = []
    after = None
    while True:
        extra = {
            "fields": "id,caption,media_type,media_product_type,permalink,timestamp",
            "limit": "50",
        }
        if after:
            extra["after"] = after
        data = graph(token, f"{ig_id}/media", extra)
        rows.extend(data.get("data") or [])
        after = ((data.get("paging") or {}).get("cursors") or {}).get("after")
        if not after or not data.get("data"):
            break
    return rows


def insights_for(token: str, media_id: str) -> dict[str, int]:
    try:
        data = graph(token, f"{media_id}/insights", {"metric": "reach,saved,shares,views"})
    except RuntimeError:
        data = graph(token, f"{media_id}/insights", {"metric": "reach,saved,shares"})
    out: dict[str, int] = {}
    for row in data.get("data") or []:
        values = row.get("values") or [{}]
        out[str(row.get("name"))] = int(values[0].get("value") or 0)
    return out


def ch_query(sql: str, stdin: str | None = None) -> str:
    proc = subprocess.run(
        [*CH, "-q", sql],
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"clickhouse failed: {sql[:80]}")
    return proc.stdout


def main() -> int:
    cfg = load_cfg()
    token = cfg["access_token"]
    ig_id = cfg["business_account_id"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    media = all_media(token, ig_id)
    media_lines = []
    insight_lines = []
    for item in media:
        ts = (item.get("timestamp") or "").replace("T", " ").replace("+0000", "")
        media_lines.append(
            json.dumps(
                {
                    "id": item.get("id") or "",
                    "caption": item.get("caption") or "",
                    "timestamp": ts,
                    "media_type": item.get("media_product_type") or item.get("media_type") or "",
                    "permalink": item.get("permalink") or "",
                    "_airbyte_extracted_at": now,
                },
                ensure_ascii=False,
            )
        )
        vals = insights_for(token, item["id"])
        insight_lines.append(
            json.dumps(
                {
                    "id": item["id"],
                    "reach": int(vals.get("reach") or 0),
                    "saved": int(vals.get("saved") or 0),
                    "shares": int(vals.get("shares") or 0),
                    "total_interactions": 0,
                    "views": int(vals.get("views") or 0),
                    "_airbyte_extracted_at": now,
                }
            )
        )

    ch_query("TRUNCATE TABLE analytics.raw_instagram_media")
    if media_lines:
        ch_query(
            "INSERT INTO analytics.raw_instagram_media FORMAT JSONEachRow",
            "\n".join(media_lines) + "\n",
        )
    ch_query("TRUNCATE TABLE analytics.raw_instagram_media_insights")
    if insight_lines:
        ch_query(
            "INSERT INTO analytics.raw_instagram_media_insights FORMAT JSONEachRow",
            "\n".join(insight_lines) + "\n",
        )
    subprocess.check_call(
        [
            "docker",
            "exec",
            "content-metrics-app-1",
            "sh",
            "-c",
            'cd /app && python3 -c "from app.refresh_service import run_refresh_cycle; print(run_refresh_cycle())"',
        ]
    )
    mart = ch_query(
        "SELECT platform, count(), sum(views) FROM analytics.mart_videos "
        "WHERE platform = 'instagram' GROUP BY platform"
    )
    print(f"synced {len(media)} media")
    print(mart.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
