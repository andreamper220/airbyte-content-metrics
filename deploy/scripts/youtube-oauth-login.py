#!/usr/bin/env python3
"""Obtain a YouTube OAuth refresh token with youtube.force-ssl for dashboard comments.

Usage (from deploy/):
  python3 scripts/youtube-oauth-login.py --paste

Uses YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET or GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET.
The Google Cloud OAuth client must allow the redirect URI (default: http://127.0.0.1:18743).
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 18743


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def exchange_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict:
    body = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"Token exchange failed ({exc.code}): {detail}") from exc


def print_token(payload: dict) -> None:
    refresh = payload.get("refresh_token")
    if not refresh:
        raise RuntimeError(
            "No refresh_token in response. Re-run with prompt=consent and access_type=offline."
        )
    print()
    print("Add to .env:")
    print(f"YOUTUBE_REFRESH_TOKEN={refresh}")
    print()
    print("Then restart the dashboard container.")


def authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    return f"{AUTH_URL}?{params}"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    env = load_env(root / ".env")
    parser = argparse.ArgumentParser(description="YouTube comment OAuth (youtube.force-ssl)")
    parser.add_argument(
        "--client-id",
        default=os.environ.get("YOUTUBE_CLIENT_ID")
        or env.get("YOUTUBE_CLIENT_ID")
        or env.get("GOOGLE_CLIENT_ID", ""),
    )
    parser.add_argument(
        "--client-secret",
        default=os.environ.get("YOUTUBE_CLIENT_SECRET")
        or env.get("YOUTUBE_CLIENT_SECRET")
        or env.get("GOOGLE_CLIENT_SECRET", ""),
    )
    parser.add_argument(
        "--redirect-uri",
        default=os.environ.get("YOUTUBE_REDIRECT_URI") or f"http://{CALLBACK_HOST}:{CALLBACK_PORT}",
    )
    parser.add_argument("--paste", action="store_true", help="Paste the redirect URL (default)")
    parser.add_argument("--serve", action="store_true", help="Catch the redirect on localhost")
    args = parser.parse_args()
    if not args.client_id or not args.client_secret:
        print("Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET (or GOOGLE_*).")
        return 1

    state = secrets.token_urlsafe(24)
    url = authorize_url(args.client_id, args.redirect_uri, state)
    if args.serve:
        result: dict[str, str] = {}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *items) -> None:
                return

            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                query = urllib.parse.parse_qs(parsed.query)
                code = (query.get("code") or [""])[0]
                got_state = (query.get("state") or [""])[0]
                if got_state != state:
                    self.send_response(400)
                    self.end_headers()
                    result["error"] = "state mismatch"
                    return
                result["code"] = code
                body = b"<html><body><h2>YouTube token received</h2><p>Return to the terminal.</p></body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = HTTPServer((CALLBACK_HOST, CALLBACK_PORT), Handler)
        print("Open in the YouTube channel Google account:")
        print(url)
        print()
        print(f"Waiting on {args.redirect_uri} ...")
        server.handle_request()
        server.server_close()
        if result.get("error") or not result.get("code"):
            print(result.get("error") or "No code in callback")
            return 1
        payload = exchange_code(args.client_id, args.client_secret, result["code"], args.redirect_uri)
        print_token(payload)
        return 0

    print("1. Open this URL (YouTube channel Google account):")
    print(url)
    print()
    print("2. After Allow, paste the FULL redirect URL and press Enter:")
    try:
        callback = input().strip()
    except EOFError:
        return 1
    parsed = urllib.parse.urlparse(callback)
    query = urllib.parse.parse_qs(parsed.query)
    code = (query.get("code") or [""])[0]
    if not code:
        print("No code= in URL")
        return 1
    payload = exchange_code(args.client_id, args.client_secret, code, args.redirect_uri)
    print_token(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
