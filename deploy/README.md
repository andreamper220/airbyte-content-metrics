# Unified VPS deploy: Airbyte + Content Analytics

Один скрипт поднимает **весь стек** на VPS. Важно понимать, как он устроен:

| Компонент | Как запускается |
|-----------|-----------------|
| ClickHouse | `docker compose` |
| Дашборд (FastAPI + React SPA) | `docker compose` (multi-stage build) |
| Кастомный TikTok-коннектор | `docker compose build` (образ из этого репо) |
| **Airbyte OSS** | **abctl** → kind-кластер в Docker (официальный способ) |

Airbyte **нельзя** положить в обычный `docker-compose.yml` — upstream [больше не поддерживает](https://docs.airbyte.com/platform/deploying-airbyte/migrating-from-docker-compose) compose-деплой. Поэтому «единый стек» = **один `bootstrap.sh`**, который оркестрирует compose + abctl.

## Фронтенд (React + shadcn/ui)

Дашборд — SPA в `content-analytics/frontend/` (Vite, Tailwind, shadcn/ui).

При `docker compose up --build` образ `app` собирается в два этапа:

1. **Node 22** — `npm ci && npm run build` → `frontend/dist`
2. **Python 3.12** — FastAPI отдаёт статику и API (`/api/*`, `/health`)

**На VPS Node.js ставить не нужно** — он используется только внутри Docker на этапе сборки.

После изменений во `frontend/`:

```bash
docker compose up -d --build
```

Локальная разработка UI без пересборки образа — см. `content-analytics/SETUP.md` (`npm run dev` на порту 5173).

## Схема

```
┌──────────────────────────────────────────────────────────────┐
│ VPS                                                          │
│                                                              │
│  ./bootstrap.sh                                              │
│       │                                                      │
│       ├─► docker compose (deploy/docker-compose.yml)         │
│       │      ├─ clickhouse :8123  ──┐                        │
│       │      └─ app :8080           │                        │
│       │           ├─ FastAPI (API)  │  Airbyte destination   │
│       │           └─ frontend/dist  │                        │
│       │              (React SPA)    │                        │
│       ├─► docker compose build       │                       │
│       │      source-tiktok-business  │                       │
│       │                              │                       │
│       └─► abctl local install        │                       │
│              └─ kind cluster         │                       │
│                   └─ airbyte/* pods ─┘                       │
│                                                              │
│  nginx :443 → dashboard :8080 (SPA + /api/*)                 │
│  nginx :443 → Airbyte UI :8000 (опционально)                 │
└──────────────────────────────────────────────────────────────┘
```

## Требования к VPS

- Ubuntu 22.04+ (или любой Linux с Docker)
- **минимум 4 GB RAM** (abctl + kind + ClickHouse; комфортно 8 GB)
- Docker Engine + Compose v2
- Открытые порты: 22, 80/443 (nginx), 8000 (Airbyte UI, если без nginx)

Для **сборки образа** на VPS (не для runtime): Docker скачает Node-образ ~200 MB при первом `docker compose build`.

## Быстрый старт

```bash
git clone <repo-url> airbyte-content-metrics
cd airbyte-content-metrics/deploy

cp .env.example .env
nano .env   # пароль ClickHouse, домен AIRBYTE_HOST

chmod +x bootstrap.sh
./bootstrap.sh
```

Только аналитика без Airbyte:

```bash
./bootstrap.sh --analytics-only
```

Проверка:

```bash
curl http://127.0.0.1:8080/health          # {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/   # 200
```

## Переменные `.env`

| Переменная | Назначение |
|------------|------------|
| `CLICKHOUSE_PASSWORD` | Пароль БД (обязателен) |
| `CLICKHOUSE_HOST_BIND` | `0.0.0.0` для abctl на том же VPS; `127.0.0.1` если Airbyte на другой машине |
| `AIRBYTE_CLICKHOUSE_HOST` | Host в UI Airbyte для destination (`172.17.0.1` на Linux, `host.docker.internal` на Docker Desktop) |
| `AIRBYTE_HOST` | FQDN VPS для abctl ingress |
| `AIRBYTE_PORT` | Порт UI Airbyte (по умолчанию 8000) |
| `APP_PORT` | Порт дашборда на хосте (по умолчанию 8080) |
| `APP_HOST_BIND` | Адрес привязки дашборда (`127.0.0.1` — только nginx снаружи) |

## Настройка Airbyte после bootstrap

### 1. Destination: ClickHouse

| Поле | Значение |
|------|----------|
| Host | `AIRBYTE_CLICKHOUSE_HOST` из `.env` |
| Port | `8123` |
| Database | `analytics` |
| User / Password | из `.env` |

### 2. Sources

**Из каталога** (образы с Docker Hub):

- `source-youtube-data` → `raw_youtube_videos`
- `source-instagram` → `raw_instagram_media`, `raw_instagram_media_insights`
- `source-yandex-metrica` → `raw_metrika_sessions`
- `source-google-analytics-data-api` → `raw_ga4_sessions`

**Кастомный** (из этого репо):

1. Airbyte UI → Settings → Sources → **Add Docker connector**
2. Image: `airbyte/source-tiktok-business:dev`
3. Connection → таблица `raw_tiktok_videos`

### 3. После синка

```bash
curl -X POST http://127.0.0.1:8080/api/refresh
```

Или кнопка **«Обновить данные»** на дашборде.

Маппинг UTM: http://127.0.0.1:8080/settings

## Nginx (HTTPS)

Проксируйте и статику, и API одним `location /` — SPA и `/api/*` на одном порту:

```nginx
# analytics.example.com → dashboard (React SPA + API)
server {
    listen 443 ssl;
    server_name analytics.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# airbyte.example.com → Airbyte UI
server {
    listen 443 ssl;
    server_name airbyte.example.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
}
```

При установке abctl укажите `--host airbyte.example.com`.

## Обновление

```bash
cd deploy
git pull

# обязательно --build, если менялся frontend/ или app/
docker compose up -d --build

docker compose --profile build-connectors build source-tiktok-business
kind load docker-image airbyte/source-tiktok-business:dev -n airbyte-abctl
```

## Частые проблемы

| Симптом | Решение |
|---------|---------|
| 503 «Frontend build not found» | `docker compose up -d --build` |
| Старый UI после деплоя | Не хватило `--build`; очистите кэш браузера |
| `npm ci` падает при сборке | Проверьте `frontend/package-lock.json` в git |
| Пустая страница, API работает | Откройте DevTools → Network; проверьте `/assets/*` |

## Связь с `content-analytics/docker-compose.yml`

- **`deploy/docker-compose.yml`** — канонический prod-файл для VPS (весь стек данных).
- **`content-analytics/docker-compose.yml`** — тот же образ `app`, для локальной разработки.

Подробнее по источникам, таблицам и локальному dev: `content-analytics/SETUP.md`.
