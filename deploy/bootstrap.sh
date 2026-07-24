#!/usr/bin/env bash
# One-command VPS bootstrap: analytics stack + Airbyte OSS (abctl) + custom connectors.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Create .env first: cp .env.example .env && nano .env"
  exit 1
fi

# shellcheck disable=SC1091
set -a && source .env && set +a

ANALYTICS_ONLY=0
SKIP_AIRBYTE=0
SKIP_CONNECTORS=0

for arg in "$@"; do
  case "$arg" in
    --analytics-only) ANALYTICS_ONLY=1 ;;
    --skip-airbyte) SKIP_AIRBYTE=1 ;;
    --skip-connectors) SKIP_CONNECTORS=1 ;;
    -h|--help)
      cat <<'EOF'
Usage: ./bootstrap.sh [options]

  (no flags)           Start ClickHouse + dashboard, build TikTok connector, install Airbyte
  --analytics-only     Only docker compose up (no abctl, no connector build)
  --skip-airbyte       Skip abctl local install
  --skip-connectors    Skip custom connector image build/load

EOF
      exit 0
      ;;
  esac
done

echo "==> Starting ClickHouse + dashboard"
docker compose up -d --build

if [[ "$ANALYTICS_ONLY" -eq 1 ]]; then
  echo "Analytics stack is up."
  echo "Dashboard: http://127.0.0.1:${APP_PORT:-8080}"
  exit 0
fi

if [[ "$SKIP_CONNECTORS" -eq 0 ]]; then
  echo "==> Building custom connector: source-tiktok-business"
  docker compose --profile build-connectors build source-tiktok-business
fi

if [[ "$SKIP_AIRBYTE" -eq 0 ]]; then
  if ! command -v abctl >/dev/null 2>&1; then
    echo "==> Installing abctl"
    curl -LsfS https://get.airbyte.com | bash -
  fi

  ABCTL_ARGS=(local install --host "${AIRBYTE_HOST:?Set AIRBYTE_HOST in .env}")

  if [[ -n "${AIRBYTE_PORT:-}" ]]; then
    ABCTL_ARGS+=(--port "$AIRBYTE_PORT")
  fi

  if [[ "${AIRBYTE_INSECURE_COOKIES:-0}" == "1" ]]; then
    ABCTL_ARGS+=(--insecure-cookies)
  fi

  echo "==> Installing Airbyte OSS (abctl → kind cluster)"
  abctl "${ABCTL_ARGS[@]}"

  if [[ "$SKIP_CONNECTORS" -eq 0 ]]; then
    CLUSTER="${AIRBYTE_KIND_CLUSTER:-airbyte-abctl}"
    IMAGE="airbyte/source-tiktok-business:${TIKTOK_CONNECTOR_TAG:-dev}"
    if command -v kind >/dev/null 2>&1; then
      echo "==> Loading $IMAGE into kind cluster $CLUSTER"
      kind load docker-image "$IMAGE" -n "$CLUSTER"
    else
      echo "WARN: kind CLI not found; load the connector image manually:"
      echo "  kind load docker-image $IMAGE -n $CLUSTER"
    fi
  fi
fi

cat <<EOF

Done.

Dashboard (put nginx in front):
  http://127.0.0.1:${APP_PORT:-8080}
  curl http://127.0.0.1:${APP_PORT:-8080}/health

Airbyte UI:
  http://${AIRBYTE_HOST}:${AIRBYTE_PORT:-8000}

Airbyte → ClickHouse destination:
  Host:     ${AIRBYTE_CLICKHOUSE_HOST:-172.17.0.1}
  Port:     8123
  Database: ${CLICKHOUSE_DATABASE:-analytics}
  User:     ${CLICKHOUSE_USER:-default}
  Password: (from .env)

Custom TikTok source (register once in Airbyte UI):
  Image: airbyte/source-tiktok-business:${TIKTOK_CONNECTOR_TAG:-dev}

Catalog sources (pull from Docker Hub, no build needed):
  - airbyte/source-youtube-data
  - airbyte/source-instagram
  - airbyte/source-yandex-metrica
  - airbyte/source-google-analytics-data-api
  - airbyte/destination-clickhouse

After each Airbyte sync:
  curl -X POST http://127.0.0.1:${APP_PORT:-8080}/api/refresh

EOF
