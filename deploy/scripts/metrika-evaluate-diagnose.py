#!/usr/bin/env python3
"""Simulate Airbyte Yandex Metrica check_connection evaluate calls."""
import json
import pathlib
import re
import urllib.parse
import urllib.request

TOKEN = pathlib.Path("/var/www/content/deploy/secrets/source-metrika-config.json").read_text()
TOKEN = json.loads(TOKEN)["auth_token"]
COUNTER = "107006450"
START = "2025-01-01"
END = "2025-09-15"
BASE = f"https://api-metrika.yandex.net/management/v1/counter/{COUNTER}/logrequests/evaluate"
SCHEMA_DIR = pathlib.Path("/tmp")


def evaluate(source: str, schema_file: str) -> None:
    props = json.loads((SCHEMA_DIR / schema_file).read_text())["properties"]
    fields = ",".join(props.keys())
    params = urllib.parse.urlencode(
        {"date1": START, "date2": END, "source": source, "fields": fields},
        quote_via=urllib.parse.quote,
    )
    req = urllib.request.Request(
        f"{BASE}?{params}",
        headers={"Authorization": f"Bearer {TOKEN}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read())
            ev = body.get("log_request_evaluation", {})
            print(schema_file, "possible=", ev.get("possible"), "expected_size=", ev.get("expected_size"))
    except urllib.error.HTTPError as exc:
        err = exc.read().decode(errors="replace")[:500]
        print(schema_file, "HTTP", exc.code, err)


if __name__ == "__main__":
    evaluate("visits", "sessions.json")
    evaluate("hits", "views.json")
