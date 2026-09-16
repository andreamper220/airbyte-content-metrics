#!/usr/bin/env python3
"""Inspect Airbyte + VK connector state on VPS."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request

HOST = "content.netvolk.online"
BASE = "http://127.0.0.1:18091/api/v1"


def abctl_creds() -> tuple[str, str, str, str]:
    raw = subprocess.check_output(["abctl", "local", "credentials"], stderr=subprocess.STDOUT, text=True)
    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    email = password = client_id = client_secret = ""
    for line in clean.splitlines():
        if "Email:" in line:
            email = line.split("Email:", 1)[1].strip()
        if "Password:" in line:
            password = line.split("Password:", 1)[1].strip()
        if "Client-Id:" in line:
            client_id = line.split("Client-Id:", 1)[1].strip()
        if "Client-Secret:" in line:
            client_secret = line.split("Client-Secret:", 1)[1].strip()
    return email, password, client_id, client_secret


def post(path: str, payload: dict, headers: dict | None = None) -> tuple[int, str]:
    h = {"Content-Type": "application/json", "Host": HOST}
    if headers:
        h.update(headers)
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode(),
        headers=h,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def main() -> int:
    email, password, client_id, client_secret = abctl_creds()
    print("=== Application token → workspaces/list ===")
    code, body = post("/applications/token", {"client_id": client_id, "client_secret": client_secret})
    print("token status", code)
    if code != 200:
        print(body[:300])
        return 1
    app_token = json.loads(body)["access_token"]
    code, body = post("/workspaces/list", {}, {"Authorization": f"Bearer {app_token}"})
    print("workspaces/list", code, body[:200])

    print("\n=== User login → workspaces/list ===")
    code, body = post("/users/login", {"email": email, "password": password})
    print("login", code, body[:250])
    if code != 200:
        return 1
    login = json.loads(body)
    user_token = login.get("accessToken") or login.get("token") or ""
    if not user_token and "user" in login:
        user_token = login.get("accessToken", "")
    # Airbyte versions differ
    for key in ("accessToken", "token", "bearerToken"):
        if login.get(key):
            user_token = login[key]
            break
    if not user_token:
        print("No user token in login response keys:", list(login.keys()))
        # try cookie-based - print full response structure without password
        user_token = app_token  # fallback

    auth_header = {"Authorization": f"Bearer {user_token}"}
    code, body = post("/workspaces/list", {}, auth_header)
    print("workspaces/list (user)", code, body[:400])
    if code != 200:
        return 1

    ws = json.loads(body)["workspaces"][0]["workspaceId"]
    code, body = post("/connections/list", {"workspaceId": ws}, auth_header)
    print("\n=== Connections ===")
    print("status", code)
    data = json.loads(body)
    for c in data.get("connections", []):
        print("-", c.get("name"), c.get("connectionId"), "status", c.get("status"))

    code, body = post("/sources/list", {"workspaceId": ws}, auth_header)
    print("\n=== Sources ===")
    for s in json.loads(body).get("sources", []):
        print("-", s.get("name"), s.get("sourceId"), s.get("sourceDefinitionId"))

    vk_sources = [s for s in json.loads(body).get("sources", []) if "vk" in s.get("name", "").lower()]
    if vk_sources:
        sid = vk_sources[0]["sourceId"]
        code, body = post("/sources/check_connection", {"sourceId": sid}, auth_header)
        print("\n=== VK source check_connection ===", code, body[:300])
        conn = next((c for c in data.get("connections", []) if c.get("sourceId") == sid), None)
        if conn:
            cid = conn["connectionId"]
            code, body = post("/connections/sync", {"connectionId": cid}, auth_header)
            print("sync triggered", code, body[:200])
    else:
        print("\nNo VK source in Airbyte yet — create via UI (API app token blocked on workspaces).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
