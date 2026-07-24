# Content Analytics

Встроенный дашборд вместо Grafana: FastAPI + ClickHouse.

## Архитектура

```
Airbyte → ClickHouse (raw_*) → POST /api/refresh → mart_* → Dashboard
```

Корреляция **без content_map**: по `utm_source` + дате публикации/дня.
Настройте маппинг в `clickhouse/init.sql` → `v_platform_utm_map`.

## Запуск

**Локально (только дашборд + ClickHouse):**

```bash
cd content-analytics
cp .env.example .env   # задайте CLICKHOUSE_PASSWORD
docker compose up -d --build
# Дашборд: http://localhost:8080
```

**VPS: полный стек (Airbyte + ClickHouse + дашборд + TikTok-коннектор):**

```bash
cd deploy
cp .env.example .env
./bootstrap.sh
```

См. `deploy/README.md`.

Локально без Docker:

```bash
pip install -e .
uvicorn app.main:app --reload --port 8080
```

UI на React + shadcn/ui (`frontend/`):

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173 (API проксируется на :8080)
```

Продакшен-сборка фронтенда:

```bash
cd frontend
npm run build
# FastAPI отдаёт frontend/dist
```

## После синка Airbyte

1. Airbyte пишет в `analytics.raw_*` таблицы
2. Нажмите «Обновить данные» на дашборде (или `POST /api/refresh`)
3. Marts пересчитываются, дашборд обновляется

## Airbyte connections

| Source | Destination table |
|--------|-------------------|
| source-tiktok-business → videos | raw_tiktok_videos |
| source-youtube-data → videos | raw_youtube_videos |
| source-instagram → media + media_insights | raw_instagram_media, raw_instagram_media_insights |
| source-google-analytics-data-api | raw_ga4_sessions |
| source-yandex-metrica → sessions | raw_metrika_sessions |

В GA4 отчёте включите dimensions: `date`, `sessionSource`, `sessionMedium`, `sessionManualTerm`, `landingPage`.
В Метрике: `UTMSource`, `UTMMedium`, `UTMContent`, `startURL`.

## UTM без utm_campaign

Связь идёт через `utm_source` (youtube/tiktok/instagram) + `utm_medium` + дату.
Точность: видно, что TikTok принёс трафик в день вирусного ролика, но не 1:1 привязку к конкретному video_id без utm_content.

Если используете `utm_content` с ID ролика — добавьте join в `v_viral_candidates`.
