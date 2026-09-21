#!/usr/bin/env python3
"""Exchange a short-lived Instagram/Facebook user token for a long-lived one."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SECRET = Path("/var/www/content/deploy/secrets/source-instagram-config.json")
GRAPH = "https://graph.facebook.com/v21.0"


def graph(path: str, query: dict) -> dict:
    url = f"{GRAPH}/{path}?{urllib.parse.urlencode(query)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode(errors="replace")[:800]) from exc


def main() -> int:
    cfg = json.loads(SECRET.read_text())
    token = cfg["access_token"]
    app_id = cfg["client_id"]
    app_secret = cfg["client_secret"]
    data = graph(
        "oauth/access_token",
        {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": token,
        },
    )
    new_token = data.get("access_token")
    if not new_token:
        raise SystemExit(f"exchange failed: {list(data)}")
    cfg["access_token"] = new_token
    SECRET.write_text(json.dumps(cfg, indent=2) + "\n")
    SECRET.chmod(0o600)

    debug = graph("debug_token", {"input_token": new_token, "access_token": f"{app_id}|{app_secret}"}).get("data") or {}
    expires = debug.get("expires_at") or 0
    when = datetime.fromtimestamp(expires, timezone.utc).isoformat() if expires else "unknown"
    print("ok")
    print("is_valid", debug.get("is_valid"))
    print("type", debug.get("type"))
    print("expires_at", when)
    print("token_len", len(new_token))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
