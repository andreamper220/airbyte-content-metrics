#!/usr/bin/env python3
import json
from pathlib import Path

path = Path("/var/www/content/deploy/secrets/source-metrika-config.json")
config = json.loads(path.read_text())
config["start_date"] = "2026-01-01"
path.write_text(json.dumps(config, indent=2) + "\n")
print(config)
