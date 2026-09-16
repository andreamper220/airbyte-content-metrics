#!/usr/bin/env python3
"""Drop manually-created Dzen table so Airbyte can recreate it."""
import subprocess

sql = "DROP TABLE IF EXISTS analytics.raw_dzen_shorts"
subprocess.check_call(
    ["docker", "exec", "content-metrics-clickhouse-1", "clickhouse-client", "--query", sql]
)
print("dropped raw_dzen_shorts")
