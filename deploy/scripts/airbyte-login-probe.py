#!/usr/bin/env python3
import json
import re
import subprocess
import urllib.request
import urllib.error

raw = subprocess.check_output(["abctl", "local", "credentials"], stderr=subprocess.STDOUT, text=True)
clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
email = password = ""
for line in clean.splitlines():
    if "Email:" in line:
        email = line.split("Email:", 1)[1].strip()
    if "Password:" in line:
        password = line.split("Password:", 1)[1].strip()

payload = json.dumps({"email": email, "password": password}).encode()
for base, host in [
    ("http://127.0.0.1:18091/api/v1", "content.netvolk.online"),
    ("http://127.0.0.1:18091/api/v1", None),
    ("http://127.0.0.1:8000/api/v1", "content.netvolk.online"),
    ("http://127.0.0.1:8000/api/v1", None),
]:
    headers = {"Content-Type": "application/json"}
    if host:
        headers["Host"] = host
    req = urllib.request.Request(f"{base}/users/login", data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print("OK", base, host, resp.status)
    except urllib.error.HTTPError as e:
        print("FAIL", base, host, e.code)
