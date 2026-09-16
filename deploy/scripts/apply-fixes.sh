docker exec -i content-metrics-clickhouse-1 clickhouse-client --multiquery < /var/www/content/deploy/scripts/fix-mart-view.sql
python3 <<'PY'
import json
p = "/var/www/content/deploy/secrets/source-vk-config.json"
d = json.load(open(p))
d["max_short_duration_seconds"] = 3600
json.dump(d, open(p, "w"), indent=2, ensure_ascii=False)
open(p, "a").write("\n")
print("vk config max duration", d["max_short_duration_seconds"])
PY
cd /var/www/content/deploy
SKIP_CONNECTOR_BUILD=1 python3 scripts/setup-vk-dzen.py --dzen-only
