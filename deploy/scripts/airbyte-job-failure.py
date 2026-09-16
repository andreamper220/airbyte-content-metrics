#!/usr/bin/env python3
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

p = Path("/var/www/content/deploy/scripts/setup-vk-dzen.py")
spec = importlib.util.spec_from_file_location("setup", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
root = Path("/var/www/content/deploy")
env = mod.load_env(root / ".env")
client = mod.AirbyteClient(
    env.get("AIRBYTE_HOST", "content.netvolk.online"),
    env["AIRBYTE_CLIENT_ID"],
    env["AIRBYTE_CLIENT_SECRET"],
    workspace_id=env.get("AIRBYTE_WORKSPACE_ID", "3f56ead9-e8a3-496d-a96d-98fd18e7d52c"),
    email=env.get("AIRBYTE_USERNAME", ""),
    password=env.get("AIRBYTE_PASSWORD", ""),
)
conn_id = sys.argv[1] if len(sys.argv) > 1 else "04cc73fa-639f-49ea-8e73-3df5551cef38"
jobs = client.call("/jobs/list", {"configTypes": ["sync"], "configId": conn_id, "limit": 1})
job = jobs["jobs"][0]["job"]
attempt = jobs["jobs"][0]["attempts"][0]
print("job", job["id"], job["status"], "emitted", job["aggregatedStats"].get("recordsEmitted"))
fs = attempt.get("failureSummary") or {}
for f in fs.get("failures") or []:
    print("FAIL:", f.get("internalMessage") or f.get("externalMessage"))
