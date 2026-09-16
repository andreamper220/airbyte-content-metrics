# Развёртывание на VPS (Docker) — пошагово

Инструкция для человека без опыта: от чистого сервера до работающего дашборда с YouTube, TikTok, Instagram и Яндекс.Метрикой.

---

## Что получится в итоге

| Сервис | Где открывается | Зачем |
|--------|-----------------|-------|
| **Дашборд** | `https://analytics.ваш-домен.ru` | Графики, корреляция, топ роликов |
| **Airbyte** | `https://airbyte.ваш-домен.ru` | Сбор данных из соцсетей и Метрики |
| **ClickHouse** | только внутри VPS (порт 8123) | База данных, сюда пишет Airbyte |

Дашборд **сам обновляет витрины** каждые 15 минут. Кнопка «Обновить данные» — для ручного запуска.

---

## Шаг 0. Что нужно заранее

### Сервер (VPS)

- **ОС:** Ubuntu 22.04 или 24.04
- **RAM:** минимум 4 GB (лучше 8 GB, если Airbyte на том же сервере)
- **Диск:** от 40 GB SSD
- **Доступ:** SSH под пользователем с `sudo`

### Домен (желательно)

- `analytics.example.com` → дашборд
- `airbyte.example.com` → панель Airbyte

### Аккаунты API

- Google Cloud (YouTube)
- TikTok for Developers (Business)
- Meta Developers (Instagram Business)
- Яндекс.Метрика + OAuth-токен

---

## Шаг 1. Подключиться к VPS

На своём компьютере (PowerShell / Terminal):

```bash
ssh root@IP_ВАШЕГО_VPS
```

Замените `IP_ВАШЕГО_VPS` на реальный IP из письма хостинга.

---

## Шаг 2. Установить Docker

На VPS выполните по очереди:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y ca-certificates curl git

curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

Выйдите из SSH и зайдите снова (чтобы группа `docker` применилась):

```bash
exit
ssh root@IP_ВАШЕГО_VPS
docker --version
docker compose version
```

Должны показаться версии Docker и Compose v2.

---

## Шаг 3. Скачать проект

```bash
cd /opt
sudo git clone https://github.com/ВАШ_АККАУНТ/airbyte-content-metrics.git
sudo chown -R $USER:$USER airbyte-content-metrics
cd airbyte-content-metrics/deploy
```

Если репозиторий приватный — используйте deploy key или personal access token.

---

## Шаг 4. Создать файл настроек `.env`

```bash
cp .env.example .env
nano .env
```

**Обязательно измените:**

| Строка в `.env` | Что написать | Пример |
|-----------------|--------------|--------|
| `CLICKHOUSE_PASSWORD` | Надёжный пароль | `MyStr0ng_Pass_2026!` |
| `AIRBYTE_HOST` | Домен для Airbyte UI | `airbyte.example.com` |
| `CLICKHOUSE_HOST_BIND` | `0.0.0.0` (Airbyte на том же VPS) | `0.0.0.0` |
| `AIRBYTE_CLICKHOUSE_HOST` | IP docker-моста на Linux | `172.17.0.1` |

Сохранить в nano: `Ctrl+O`, Enter, `Ctrl+X`.

---

## Шаг 5. Запустить стек (вариант А — только дашборд)

Если Airbyte уже есть на другой машине или настроите позже:

```bash
chmod +x bootstrap.sh
./bootstrap.sh --analytics-only
```

Подождите 3–10 минут (первая сборка образа скачивает Node и Python).

**Проверка:**

```bash
curl http://127.0.0.1:8080/health
```

Ответ: `{"status":"ok"}`

---

## Шаг 5. Запустить стек (вариант Б — дашборд + Airbyte)

Полный стек (нужно 4–8 GB RAM):

```bash
chmod +x bootstrap.sh
./bootstrap.sh
```

Скрипт:

1. Соберёт и запустит **ClickHouse** + **дашборд** в Docker
2. Соберёт кастомный коннектор **TikTok**
3. Установит **Airbyte** через `abctl` (kind-кластер в Docker)

Первая установка Airbyte может занять **20–40 минут**.

После завершения:

```bash
curl http://127.0.0.1:8080/health
abctl local credentials   # логин/пароль для Airbyte UI
```

Airbyte UI: `http://IP_VPS:8000` (позже — через nginx и HTTPS).

---

## Шаг 6. Открыть дашборд снаружи (nginx + HTTPS)

Установите nginx и certbot:

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

Создайте конфиг:

```bash
sudo nano /etc/nginx/sites-available/analytics
```

Вставьте (замените домен):

```nginx
server {
    listen 80;
    server_name analytics.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Включите сайт и получите SSL:

```bash
sudo ln -s /etc/nginx/sites-available/analytics /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d analytics.example.com
```

Откройте в браузере: **https://analytics.example.com**

Аналогично для Airbyte на `airbyte.example.com` → `proxy_pass http://127.0.0.1:8000`.

**Безопасность:** в `.env` оставьте `APP_HOST_BIND=127.0.0.1` — дашборд слушает только localhost, снаружи доступ только через nginx.

---

## Шаг 7. Настроить Airbyte → ClickHouse

1. Откройте Airbyte UI
2. **Destinations** → **+ New destination** → **ClickHouse**
3. Заполните:

| Поле | Значение |
|------|----------|
| Host | `172.17.0.1` (из `.env` → `AIRBYTE_CLICKHOUSE_HOST`) |
| Port | `8123` |
| Database | `analytics` |
| Username | `default` |
| Password | из `.env` → `CLICKHOUSE_PASSWORD` |

4. **Test connection** → Save

---

## Шаг 8. Подключить источники

Создайте **4 connection** (Source → ClickHouse). Подробности по каждому API — в `content-analytics/SETUP.md`.

| Источник | Коннектор в Airbyte | Таблица в ClickHouse |
|----------|---------------------|----------------------|
| YouTube | `source-youtube-data` | `raw_youtube_videos` |
| TikTok | `airbyte/source-tiktok-business:dev` (кастом) | `raw_tiktok_videos` |
| Instagram | `source-instagram` | `raw_instagram_media`, `raw_instagram_media_insights` |
| Метрика | `source-yandex-metrica` | `raw_metrika_sessions` |

**TikTok (кастом):** Airbyte → Settings → Sources → Add Docker connector → Image: `airbyte/source-tiktok-business:dev`

Для каждого connection:

- Укажите правильное имя destination-таблицы
- Запустите **Sync now**
- Дождитесь статуса **Succeeded**

---

## Шаг 9. UTM-метки и маппинг

В ссылках на сайт из соцсетей используйте:

```
?utm_source=youtube&utm_medium=social
?utm_source=tiktok&utm_medium=social
?utm_source=instagram&utm_medium=social
```

На дашборде: **https://analytics.example.com/settings** — свяжите платформу с `utm_source`.

---

## Шаг 10. Автообновление (уже включено)

В `.env` на VPS:

```env
AUTO_REFRESH_ENABLED=true
MART_REFRESH_INTERVAL_MINUTES=15
```

Дашборд пересобирает витрины из `raw_*` каждые 15 минут.

**Опционально** — чтобы дашборд сам запускал синки Airbyte:

```env
AIRBYTE_SYNC_ENABLED=true
AIRBYTE_SYNC_INTERVAL_MINUTES=15
AIRBYTE_API_URL=http://127.0.0.1:8000
AIRBYTE_USERNAME=email@из_abctl_local_credentials
AIRBYTE_PASSWORD=пароль_из_abctl
AIRBYTE_CONNECTION_IDS=uuid1,uuid2,uuid3,uuid4
```

UUID connections: Airbyte → Connections → откройте connection → ID в URL.

Проверка статуса:

```bash
curl http://127.0.0.1:8080/api/refresh/status
```

---

## Шаг 11. Демо-данные (для проверки без API)

```bash
cd /opt/airbyte-content-metrics/content-analytics
docker cp clickhouse/seed_demo.sql content-metrics-clickhouse-1:/tmp/seed_demo.sql
bash clickhouse/reseed_demo.sh
```

Обновите страницу дашборда — появятся тестовые ролики и корреляции.

---

## Обновление после `git pull`

```bash
cd /opt/airbyte-content-metrics/deploy
git pull
docker compose up -d --build
```

Если менялся TikTok-коннектор:

```bash
docker compose --profile build-connectors build source-tiktok-business
kind load docker-image airbyte/source-tiktok-business:dev -n airbyte-abctl
```

---

## Чеклист «всё работает»

```bash
docker compose ps                    # clickhouse + app — Up (healthy)
curl http://127.0.0.1:8080/health    # {"status":"ok"}
curl http://127.0.0.1:8080/api/refresh/status
```

В ClickHouse есть данные:

```bash
docker exec content-metrics-clickhouse-1 clickhouse-client --query "SELECT count() FROM analytics.raw_youtube_videos"
```

В браузере: карточки, график, таблицы заполнены.

---

## Частые проблемы

| Проблема | Решение |
|----------|---------|
| `docker compose up --build` падает на npm | Обновите репо; в Dockerfile используется `npm install`. Добавлен `.dockerignore`. |
| Airbyte не видит ClickHouse | Проверьте `AIRBYTE_CLICKHOUSE_HOST=172.17.0.1`, пароль, `CLICKHOUSE_HOST_BIND=0.0.0.0` |
| Пустой дашборд | Airbyte sync прошёл? `curl -X POST http://127.0.0.1:8080/api/refresh` |
| Корреляция нулевая | UTM в ссылках + маппинг на `/settings` |
| Не хватает RAM | `./bootstrap.sh --analytics-only`, Airbyte на отдельном сервере |
| 502 от nginx | `docker compose ps`, `docker compose logs app` |

---

## Полезные команды

```bash
# Логи дашборда
docker compose logs -f app

# Логи ClickHouse
docker compose logs -f clickhouse

# Перезапуск
docker compose restart app

# Остановить всё
docker compose down
```

Подробнее по API источников: `content-analytics/SETUP.md`  
Краткая справка по архитектуре: `deploy/README.md`
