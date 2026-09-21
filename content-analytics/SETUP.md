# Пошаговая настройка (без Google Analytics)

Дашборд: **React + shadcn/ui** (`frontend/`), API — **FastAPI**. В Docker фронтенд собирается автоматически (`npm run build` → `frontend/dist` → отдаётся из контейнера `app`).

**Локально (Docker):** http://localhost:8080  
**VPS (полный стек):** см. `../deploy/README.md` и `./bootstrap.sh`

```bash
cd content-analytics
cp .env.example .env          # задайте CLICKHOUSE_PASSWORD
docker compose up -d --build  # --build обязателен после изменений во frontend/
docker compose ps
docker compose logs -f app
```

> Порт дашборда: **8080** (меняется через `APP_PORT` в `.env`). ClickHouse: `localhost:8123`, база `analytics`.

### Локальная разработка UI (без пересборки Docker)

Два терминала:

```bash
# Терминал 1 — API
cd content-analytics
pip install -e .
uvicorn app.main:app --reload --port 8080

# Терминал 2 — фронтенд (hot reload)
cd content-analytics/frontend
npm install
npm run dev
# http://localhost:5173 — API проксируется на :8080 (см. frontend/vite.config.ts)
```

Требования: **Node.js 22+**, **Python 3.12+**.

---

## Общая схема

```
┌─────────────┐   ┌─────────────┐   ┌──────────────┐   ┌─────────────┐   ┌─────────────┐
│   YouTube   │   │   TikTok    │   │  Instagram   │   │  VK · Dzen  │   │  Я.Метрика  │
└──────┬──────┘   └──────┬──────┘   └──────┬───────┘   └──────┬──────┘   └──────┬──────┘
       │                 │                  │                  │
       └─────────────────┴──────────────────┴──────────────────┘
                                    │
                              Airbyte (ETL)
                                    │
                                    ▼
                         ClickHouse (analytics.raw_*)
                                    │
                         POST /api/refresh (кнопка на дашборде)
                                    │
                                    ▼
              React SPA (frontend/dist) ← FastAPI :8080
```

Корреляция: **платформа → utm_source → дата**.  
Без `utm_campaign` и без `content_map`.

---

## Шаг 0. Проверить дашборд с демо-данными

```bash
# Linux/macOS
docker compose exec -T clickhouse clickhouse-client < clickhouse/seed_demo.sql
```

```powershell
# Windows PowerShell
Get-Content clickhouse\seed_demo.sql | docker compose exec -T clickhouse clickhouse-client
```

Откройте http://localhost:8080 → **«Обновить данные»**. Должны появиться карточки, графики и таблицы.

---

## Шаг 1. Установить Airbyte

**Рекомендуется для VPS:** единый скрипт из `deploy/`:

```bash
cd deploy
cp .env.example .env
./bootstrap.sh
```

**Локально вручную** — [Airbyte OSS](https://docs.airbyte.com/using-airbyte/getting-started/oss-quickstart):

```bash
curl -LsfS https://get.airbyte.com | bash -
abctl local install
```

После установки UI обычно на **http://localhost:8000**.

---

## Шаг 2. Destination: ClickHouse

В Airbyte → **Destinations** → **ClickHouse**:

| Параметр | Значение |
|----------|----------|
| Host | `host.docker.internal` (Docker Desktop) или `172.17.0.1` (Linux) |
| Port | `8123` |
| Database | `analytics` |
| Username | `default` |
| Password | из `.env` (`CLICKHOUSE_PASSWORD`) |

**Важно:** для каждого connection задайте **Namespace / Table prefix**, чтобы таблицы попали в нужные имена (см. шаги 3–6).

Либо после первого синка создайте VIEW, мапящие Airbyte-таблицы на `raw_*` (если имена отличаются).

---

## Шаг 3. YouTube

### Что нужно заранее

1. [Google Cloud Console](https://console.cloud.google.com/) → проект
2. Включить **YouTube Data API v3** и **YouTube Analytics API**
3. OAuth 2.0 credentials (Desktop или Web)
4. ID канала(ов)

### Sources в Airbyte

**A) `YouTube Data`** (`source-youtube-data`)

| Stream | Зачем | Метрики |
|--------|-------|---------|
| `videos` | список роликов | title, publishedAt, viewCount, likeCount, commentCount |

Config:
```json
{
  "credentials": { "auth_method": "oauth2.0", "client_id": "...", "client_secret": "...", "refresh_token": "..." },
  "channel_ids": ["UCxxxxxxxx"]
}
```

**B) `YouTube Analytics`** (`source-youtube-analytics`) — опционально, детальнее

| Stream | Метрики |
|--------|---------|
| `channel_basic_a3` | views, likes, comments, shares, watch time по video_id |
| другие `*_a3` / `*_a1` | удержание, демография, трафик |

### Destination mapping

| Airbyte stream | ClickHouse table |
|----------------|------------------|
| `videos` (youtube-data) | `raw_youtube_videos` |

Нужные поля в `raw_youtube_videos`:
- `id`, `title`, `published_at`, `view_count`, `like_count`, `comment_count`

Если Airbyte пишет вложенный JSON (`snippet.title`, `statistics.viewCount`), добавьте нормализацию в Airbyte или SQL-view:

```sql
CREATE OR REPLACE VIEW analytics.raw_youtube_videos AS
SELECT
    id,
    JSONExtractString(_airbyte_data, 'snippet', 'title') AS title,
    parseDateTimeBestEffort(JSONExtractString(_airbyte_data, 'snippet', 'publishedAt')) AS published_at,
    toUInt64OrZero(JSONExtractString(_airbyte_data, 'statistics', 'viewCount')) AS view_count,
    toUInt64OrZero(JSONExtractString(_airbyte_data, 'statistics', 'likeCount')) AS like_count,
    toUInt64OrZero(JSONExtractString(_airbyte_data, 'statistics', 'commentCount')) AS comment_count,
    _airbyte_extracted_at
FROM analytics._airbyte_raw_videos;  -- имя уточните после первого синка
```

### Расписание

Incremental / Full refresh раз в 6–24 часа.

---

## Шаг 4. TikTok (кастомный source)

Коннектор: `airbyte-integrations/connectors/source-tiktok-business`

### Что нужно

1. [TikTok for Developers](https://developers.tiktok.com/) → приложение
2. **TikTok Business** / organic scopes (video list, account insights)
3. OAuth → `access_token`
4. `business_id` (open_id бизнес-аккаунта)

### Сборка образа для Airbyte

```bash
# из deploy/ (рекомендуется)
cd deploy
docker compose --profile build-connectors build source-tiktok-business
kind load docker-image airbyte/source-tiktok-business:dev -n airbyte-abctl
```

В Airbyte: **Settings → Sources → Add Docker connector** → `airbyte/source-tiktok-business:dev`

### Config

```json
{
  "access_token": "YOUR_TOKEN",
  "business_id": "YOUR_BUSINESS_ID",
  "start_date": "2024-01-01",
  "max_count": 20
}
```

### Streams → таблица

| Stream | ClickHouse | Метрики |
|--------|------------|---------|
| `videos` | `raw_tiktok_videos` | video_views, likes, comments, shares, reach, watch time |
| `account_profile` | *(опционально)* | followers, video_count |

### UTM в ссылках

В bio / описании используйте, например:
```
https://yoursite.com/page?utm_source=tiktok&utm_medium=social
```

---

## Шаг 5. Instagram

Source: `source-instagram` (Meta Graph API)

### Что нужно

1. [Meta Developers](https://developers.facebook.com/) → приложение
2. Instagram Graph API, permissions: `instagram_basic`, `instagram_manage_insights`, `pages_read_engagement`
3. Facebook Page, привязанная к Instagram Business/Creator
4. Long-lived access token

### Streams

| Stream | ClickHouse | Метрики |
|--------|------------|---------|
| `media` | `raw_instagram_media` | caption, timestamp, permalink, media_type |
| `media_insights` | `raw_instagram_media_insights` | reach, views, shares, saved, total_interactions |

`media_insights` — child stream, нужен parent `media`.

### UTM

```
?utm_source=instagram&utm_medium=social
```

Добавьте в `v_platform_utm_map` свои варианты (`ig`, `insta` и т.д.) — в UI: **Настройки** (`/settings`) или SQL в `clickhouse/init.sql`.

---

## Шаг 5a. VK (короткие видео / клипы)

Коннектор: `airbyte-integrations/connectors/source-vk`

### Что нужно

1. [VK для разработчиков](https://dev.vk.com/) → Web-приложение, redirect `https://ваш-домен/vk-oauth-callback`
2. **Пользовательский** access token с правом `video` (ключ из «Работа с API» в группе **не** подходит для `video.get`)
3. `owner_id` — ID сообщества со знаком `-` (напр. `-236233101`)

Получить токен без ручного PKCE: на VPS в каталоге `deploy/` задайте `VK_APP_ID` в `.env` и выполните:

```bash
python3 scripts/vk-oauth-login.py --paste
```

Откройте напечатанную ссылку → «Разрешить» → вставьте URL из адресной строки. Токен сохранится в `secrets/source-vk-config.json`.

### Сборка образа для Airbyte

```bash
cd deploy
docker compose --profile build-connectors build source-vk
kind load docker-image airbyte/source-vk:dev -n airbyte-abctl
```

В Airbyte: **Settings → Sources → Add Docker connector** → `airbyte/source-vk:dev`

### Config

```json
{
  "access_token": "YOUR_TOKEN",
  "owner_id": -123456789,
  "start_date": "2024-01-01",
  "max_short_duration_seconds": 180,
  "page_size": 100
}
```

### Streams → таблица

| Stream | ClickHouse | Метрики |
|--------|------------|---------|
| `short_videos` | `raw_vk_videos` | views, likes, comments, reposts, duration |

Синхронизируются только короткие ролики (по длительности и типу `short`/`clip`).

### UTM

```
?utm_source=vk&utm_medium=social
```

---

## Шаг 5b. Яндекс Дзен (шортсы)

Коннектор: `airbyte-integrations/connectors/source-dzen`

### Что нужно

1. Публичный канал на [dzen.ru](https://dzen.ru) — slug из URL (`https://dzen.ru/mychannel` → `mychannel`)
2. *(Опционально)* для статистики из кабинета автора: `Session_id` cookie, `x-csrf-token`, `publisherId` из URL редактора

> Официального публичного API у Дзена нет; коннектор использует те же внутренние endpoint'ы, что и веб-интерфейс.

### Сборка образа для Airbyte

```bash
cd deploy
docker compose --profile build-connectors build source-dzen
kind load docker-image airbyte/source-dzen:dev -n airbyte-abctl
```

В Airbyte: **Settings → Sources → Add Docker connector** → `airbyte/source-dzen:dev`

### Config

```json
{
  "channel_name": "mychannel",
  "session_id": "OPTIONAL_SESSION_ID",
  "csrf_token": "OPTIONAL_CSRF",
  "publisher_id": "OPTIONAL_PUBLISHER_ID",
  "start_date": "2024-01-01",
  "max_pages": 20
}
```

### Streams → таблица

| Stream | ClickHouse | Метрики |
|--------|------------|---------|
| `shorts` | `raw_dzen_shorts` | views, likes, comments (только `/shorts/`) |

### UTM

```
?utm_source=dzen&utm_medium=social
```

---

## Шаг 5c. Комментарии от имени аккаунта (YouTube / VK / Дзен)

В карточке ролика можно написать комментарий или ответить — он уходит в API площадки от имени канала.

Задайте переменные в `.env` и перезапустите `app`. Статус подключения виден в `/settings`.

| Площадка | Переменные | Как получить |
|----------|------------|--------------|
| YouTube | `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` | OAuth со scope `https://www.googleapis.com/auth/youtube.force-ssl` (токен Airbyte с readonly **не** подходит). `python3 deploy/scripts/youtube-oauth-login.py --paste` |
| VK | `VK_ACCESS_TOKEN`, `VK_OWNER_ID` | Тот же пользовательский токен, что для `source-vk`. Для сообщества `from_group=1` (по умолчанию) |
| Дзен | `DZEN_SESSION_ID`, `DZEN_CSRF_TOKEN` | Cookie `Session_id` и заголовок `x-csrf-token` из залогиненной сессии dzen.ru |

YouTube: авторизуйтесь аккаунтом канала (или Brand Account).  
VK: токену нужно право `video` (и возможность комментировать).  
Дзен: сессия периодически истекает — обновите cookie.

---

## Шаг 6. Яндекс.Метрика

Source: `source-yandex-metrica`

### Что нужно

1. Счётчик на [metrika.yandex.ru](https://metrika.yandex.ru/)
2. OAuth-токен: [получение токена](https://yandex.com/dev/metrika/doc/api2/concept/about.html)
3. `counter_id` счётчика
4. В Метрике включён **Logs API** (доступ к сырым визитам)

### Stream

| Stream | ClickHouse | Поля для корреляции |
|--------|------------|---------------------|
| `sessions` | `raw_metrika_sessions` | `UTMSource`, `UTMMedium`, `UTMContent`, `UTMCampaign`, `startURL`, `date`, `clientID`, `pageViews` |

> Таблицу `raw_metrika_sessions` создаёт **Airbyte** (нужны колонки `_airbyte_raw_id`, `_airbyte_meta`). Ручной `CREATE` из старых версий init.sql ломает синк.

Config:
```json
{
  "auth_token": "YOUR_OAUTH_TOKEN",
  "counter_id": "12345678",
  "start_date": "2024-01-01"
}
```

> Коннектор тянет **посещение-уровень** (Logs API), агрегация по дням/UTM — в `POST /api/refresh`.

### UTM

Убедитесь, что в ссылках из соцсетей есть `utm_source=youtube|tiktok|instagram|vk|dzen`.

Проверка в Метрике: Отчёты → Источники → UTM.

---

## Шаг 7. Настроить маппинг utm_source

В UI: http://localhost:8080/settings  
Или в SQL — `clickhouse/init.sql` → `v_platform_utm_map`:

```sql
CREATE OR REPLACE VIEW analytics.v_platform_utm_map AS
SELECT 'youtube' AS platform, 'youtube' AS utm_source
UNION ALL SELECT 'tiktok', 'tiktok'
UNION ALL SELECT 'tiktok', 'tt'           -- если так пишете в UTM
UNION ALL SELECT 'instagram', 'instagram'
UNION ALL SELECT 'instagram', 'ig'
UNION ALL SELECT 'vk', 'vk'
UNION ALL SELECT 'vk', 'vkontakte'
UNION ALL SELECT 'dzen', 'dzen'
UNION ALL SELECT 'dzen', 'zen'
UNION ALL SELECT 'dzen', 'yandex_zen';
```

Применить SQL:
```bash
docker compose exec -T clickhouse clickhouse-client --multiquery < clickhouse/init.sql
```

---

## Шаг 8. Первый полный цикл

1. Запустить все connections в Airbyte (Manual sync)
2. Проверить данные:
   ```sql
   SELECT count() FROM analytics.raw_tiktok_videos;
   SELECT count() FROM analytics.raw_youtube_videos;
   SELECT count() FROM analytics.raw_instagram_media;
   SELECT count() FROM analytics.raw_vk_videos;
   SELECT count() FROM analytics.raw_dzen_shorts;
   SELECT count() FROM analytics.raw_metrika_sessions;
   ```
3. Открыть http://localhost:8080 → **«Обновить данные»**
4. Смотреть:
   - карточки по платформам
   - график просмотры vs сессии
   - таблица корреляций
   - топ роликов

---

## Шаг 9. Автоматическое обновление

Дашборд **сам** пересобирает витрины (`mart_*`) из таблиц `raw_*` в ClickHouse — по умолчанию **каждые 15 минут**.

В `.env` (см. `.env.example`):

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `AUTO_REFRESH_ENABLED` | `true` | Фоновое обновление витрин |
| `MART_REFRESH_INTERVAL_MINUTES` | `15` | Интервал пересборки витрин |
| `AIRBYTE_SYNC_ENABLED` | `false` | Запускать синки Airbyte через API |
| `AIRBYTE_SYNC_INTERVAL_MINUTES` | `15` | Как часто дергать Airbyte (15 мин) |
| `AIRBYTE_API_URL` | — | Напр. `http://127.0.0.1:8000` |
| `AIRBYTE_USERNAME` / `AIRBYTE_PASSWORD` | — | Из `abctl local credentials` |
| `AIRBYTE_CONNECTION_IDS` | — | UUID connections через запятую |

Статус: `GET http://localhost:8080/api/refresh/status`

На странице дашборда отображается время последнего обновления; графики подтягиваются сами каждую минуту.

**Важно:** сырые данные в `raw_*` по-прежнему пишет **Airbyte**. Авто-refresh только пересчитывает витрины. Чтобы дашборд сам запускал синки источников — включите `AIRBYTE_SYNC_ENABLED` и укажите ID connections из Airbyte UI.

---

## Чеклист «всё работает»

| # | Проверка | Ожидание |
|---|----------|----------|
| 1 | `docker compose ps` | clickhouse healthy, app running |
| 2 | http://localhost:8080/health | `{"status":"ok"}` |
| 3 | http://localhost:8080 | React-дашборд загружается (не 503) |
| 4 | Airbyte sync YouTube | `raw_youtube_videos` > 0 строк |
| 5 | Airbyte sync TikTok | `raw_tiktok_videos` > 0 строк |
| 6 | Airbyte sync Instagram | `media` + `media_insights` > 0 |
| 7 | Airbyte sync VK | `raw_vk_videos` > 0 |
| 8 | Airbyte sync Dzen | `raw_dzen_shorts` > 0 |
| 9 | Airbyte sync Метрика | `raw_metrika_sessions` > 0 |
| 10 | UTM в Метрике | `UTMSource` = youtube/tiktok/instagram/vk/dzen |
| 11 | Refresh на дашборде | таблицы и графики заполнены |

---

## Частые проблемы

**503 «Frontend build not found»**  
→ Образ собран без фронтенда. Пересоберите: `docker compose up -d --build`.  
→ Локально без Docker: `cd frontend && npm run build`, затем `uvicorn`.

**Пустой дашборд после sync**  
→ Нажали «Обновить данные»? Имена таблиц совпадают с `raw_*`?

**Корреляция нулевая**  
→ Проверьте `utm_source` в Метрике и маппинг в `/settings` или `v_platform_utm_map`.

**TikTok API пустой ответ**  
→ Business account, правильные scopes, `business_id` = open_id.

**VK API error 15 / access denied**  
→ Проверьте scope `video` и что `owner_id` соответствует сообществу/аккаунту токена.

**Dzen sync пустой или HTTP 403**  
→ Обновите `session_id` и `csrf_token` из браузера; проверьте slug канала в `channel_name`.

**Не отправляется комментарий YouTube**  
→ Нужен refresh token со scope `youtube.force-ssl`, не readonly-токен Airbyte. Аккаунт Google должен быть связан с каналом.

**Не отправляется комментарий VK**  
→ Пользовательский токен (не ключ сообщества) с правом `video`. Для группы `VK_OWNER_ID` отрицательный.

**Не отправляется комментарий Дзена**  
→ Просрочен `DZEN_SESSION_ID` / CSRF. Скопируйте заново из DevTools на dzen.ru.

**Метрика долго синкается**  
→ Logs API асинхронный; первый запрос может ждать до 2 часов.

**Порт 8080 занят**  
→ В `.env` задайте другой `APP_PORT` и перезапустите compose.

**Изменения во `frontend/` не видны в Docker**  
→ Нужен `docker compose up -d --build`, не просто `restart`.

**`npm run build` падает локально**  
→ Node.js 22+, `npm ci` в `frontend/`. Логи: `docker compose build app`.
