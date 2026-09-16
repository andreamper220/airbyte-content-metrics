#!/usr/bin/env python3
"""
One-time VK ID login: open the printed URL, click Allow, token is saved to secrets.

VK does not allow server-only keys for video.get — a user must approve the app once.
Community keys from the group settings page do NOT work for video.get.

Usage (on the VPS, from deploy/):
  export VK_APP_ID=54774660
  python3 scripts/vk-oauth-login.py --serve

Register redirect in dev.vk.com + VK ID cabinet:
  https://content.netvolk.online/vk-oauth-callback

While --serve runs, nginx must proxy that path to 127.0.0.1:18473 (see NGINX_SNIPPET below).
Alternative without nginx:  python3 scripts/vk-oauth-login.py --paste
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

NGINX_SNIPPET = """
    location = /vk-oauth-callback {
        proxy_pass http://127.0.0.1:18473/vk-oauth-callback;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
"""

AUTH_URL = "https://id.vk.ru/authorize"
TOKEN_URL = "https://id.vk.ru/oauth2/auth"
API_VERSION = "5.199"
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 18473


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def make_pkce() -> tuple[str, str]:
    verifier = b64url(secrets.token_bytes(32))
    challenge = b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def make_state() -> str:
    return secrets.token_urlsafe(32)


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


def parse_callback_url(url: str) -> dict[str, str]:
    url = url.strip()
    if "://" not in url:
        url = "https://dummy.local/?" + url.lstrip("?")
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    fragment = urllib.parse.parse_qs(parsed.fragment, keep_blank_values=True)

    def first(params: dict[str, list[str]], key: str) -> str:
        if key in params and params[key]:
            return params[key][0]
        return ""

    code = first(query, "code") or first(fragment, "code")
    device_id = first(query, "device_id") or first(fragment, "device_id")
    state = first(query, "state") or first(fragment, "state")
    payload_raw = first(query, "payload") or first(fragment, "payload")

    if payload_raw:
        try:
            payload = json.loads(urllib.parse.unquote(payload_raw))
            code = code or str(payload.get("code") or "")
            device_id = device_id or str(payload.get("device_id") or "")
            state = state or str(payload.get("state") or "")
        except json.JSONDecodeError:
            pass

    if not code:
        raise ValueError("No authorization code in URL (expected code= or payload= with code)")

    return {"code": code, "device_id": device_id, "state": state}


def exchange_token(
    *,
    client_id: str,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    state: str,
    device_id: str,
) -> dict:
    body = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
            "state": state,
            "device_id": device_id or "local",
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


def test_video_get(access_token: str, owner_id: int) -> dict:
    params = urllib.parse.urlencode(
        {
            "access_token": access_token,
            "owner_id": owner_id,
            "count": 3,
            "v": API_VERSION,
        }
    )
    with urllib.request.urlopen(f"https://api.vk.com/method/video.get?{params}", timeout=30) as resp:
        return json.loads(resp.read().decode())


def build_authorize_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
    scope: str = "video",
) -> str:
    params = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{AUTH_URL}?{params}"


def save_config(path: Path, access_token: str, owner_id: int, start_date: str, max_duration: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "access_token": access_token,
        "owner_id": owner_id,
        "start_date": start_date,
        "max_short_duration_seconds": max_duration,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def finish_login(
    *,
    client_id: str,
    redirect_uri: str,
    owner_id: int,
    secrets_path: Path,
    start_date: str,
    max_duration: int,
    expected_state: str,
    code_verifier: str,
    callback_url: str,
) -> None:
    parsed = parse_callback_url(callback_url)
    if parsed["state"] and parsed["state"] != expected_state:
        raise RuntimeError("state mismatch — possible CSRF, aborting")

    token_response = exchange_token(
        client_id=client_id,
        code=parsed["code"],
        code_verifier=code_verifier,
        redirect_uri=redirect_uri,
        state=expected_state,
        device_id=parsed["device_id"],
    )
    access_token = token_response.get("access_token")
    if not access_token:
        raise RuntimeError(f"No access_token in response: {token_response}")

    save_config(secrets_path, access_token, owner_id, start_date, max_duration)
    print(f"Saved: {secrets_path}")

    api = test_video_get(access_token, owner_id)
    if "error" in api:
        err = api["error"]
        print(
            f"WARNING: video.get failed: {err.get('error_code')} — {err.get('error_msg')}\n"
            "If error mentions access / scope video, email devsupport@corp.vk.com to enable video for your app."
        )
    else:
        items = api.get("response", {}).get("items") or []
        print(f"OK: video.get returned {len(items)} video(s) on first page.")


def run_serve(args: argparse.Namespace) -> int:
    verifier, challenge = make_pkce()
    state = make_state()
    auth_url = build_authorize_url(args.client_id, args.redirect_uri, state, challenge, args.scope)
    done = threading.Event()
    result: dict[str, str | Exception] = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *items) -> None:
            return

        def do_GET(self) -> None:
            if not self.path.startswith("/vk-oauth-callback"):
                self.send_response(404)
                self.end_headers()
                return
            full = f"https://{args.redirect_host}{self.path}"
            try:
                finish_login(
                    client_id=args.client_id,
                    redirect_uri=args.redirect_uri,
                    owner_id=args.owner_id,
                    secrets_path=args.secrets_path,
                    start_date=args.start_date,
                    max_duration=args.max_duration,
                    expected_state=state,
                    code_verifier=verifier,
                    callback_url=full,
                )
                result["ok"] = "1"
                body = (
                    "<html><body><h2>VK token saved</h2>"
                    "<p>You can close this tab and return to the terminal.</p></body></html>"
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                result["error"] = exc
                body = f"<html><body><pre>{exc}</pre></body></html>".encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            finally:
                done.set()

    server = HTTPServer((CALLBACK_HOST, CALLBACK_PORT), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def out(msg: str = "") -> None:
        print(msg, flush=True)

    out("=== VK OAuth (automatic callback) ===")
    out("Ensure redirect is registered and nginx proxies /vk-oauth-callback (see script docstring).")
    out()
    out("Open in browser (logged in as VK group admin):")
    out(auth_url)
    out()
    out(f"Waiting on http://{CALLBACK_HOST}:{CALLBACK_PORT}/vk-oauth-callback ...")
    done.wait(timeout=600)
    server.shutdown()
    if "error" in result:
        print(result["error"])
        return 1
    if "ok" not in result:
        print("Timeout: no callback within 10 minutes.")
        return 1
    return 0


def run_paste(args: argparse.Namespace) -> int:
    verifier, challenge = make_pkce()
    state = make_state()
    auth_url = build_authorize_url(args.client_id, args.redirect_uri, state, challenge, args.scope)
    print("=== VK OAuth (paste mode) ===")
    print("1. Open this URL in the browser (VK group admin account):")
    print(auth_url)
    print()
    print("2. After Allow, copy the FULL address bar URL from the redirect page.")
    print("   Paste it here and press Enter:")
    try:
        callback_url = input().strip()
    except EOFError:
        print("No input.")
        return 1
    finish_login(
        client_id=args.client_id,
        redirect_uri=args.redirect_uri,
        owner_id=args.owner_id,
        secrets_path=args.secrets_path,
        start_date=args.start_date,
        max_duration=args.max_duration,
        expected_state=state,
        code_verifier=verifier,
        callback_url=callback_url,
    )
    return 0


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    env = load_env(root / ".env")

    parser = argparse.ArgumentParser(description="Obtain VK user token for source-vk (VK ID + PKCE)")
    parser.add_argument("--client-id", default=os.environ.get("VK_APP_ID") or env.get("VK_APP_ID", ""))
    parser.add_argument(
        "--redirect-uri",
        default=os.environ.get("VK_REDIRECT_URI")
        or env.get("VK_REDIRECT_URI", "https://content.netvolk.online/vk-oauth-callback"),
    )
    parser.add_argument(
        "--owner-id",
        type=int,
        default=int(os.environ.get("VK_OWNER_ID") or env.get("VK_OWNER_ID", "-236233101")),
    )
    parser.add_argument(
        "--secrets",
        type=Path,
        default=root / "secrets" / "source-vk-config.json",
    )
    parser.add_argument("--start-date", default=env.get("VK_START_DATE", "2024-01-01"))
    parser.add_argument("--max-duration", type=int, default=180)
    parser.add_argument("--scope", default="video")
    parser.add_argument("--serve", action="store_true", help="Wait for browser redirect via local HTTP server")
    parser.add_argument("--paste", action="store_true", help="Paste redirect URL manually (default)")
    args = parser.parse_args()

    if not args.client_id:
        print("Set VK_APP_ID in deploy/.env or pass --client-id")
        return 1

    args.secrets_path = args.secrets.resolve()
    args.redirect_host = urllib.parse.urlparse(args.redirect_uri).netloc

    if args.serve:
        return run_serve(args)
    return run_paste(args)


if __name__ == "__main__":
    raise SystemExit(main())
