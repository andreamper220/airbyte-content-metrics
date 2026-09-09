# source-dzen

Airbyte source for **Yandex Dzen short videos** (`/shorts/`).

## Streams

| Stream | Description |
|--------|-------------|
| `shorts` | Short videos from a Dzen channel with views, likes, comments |

## Data sources

1. **Public channel feed** — `GET https://dzen.ru/api/v3/launcher/more?channel_name=...`
2. **Publisher API (optional)** — authenticated requests with `session_id`, `csrf_token`, and `publisher_id`

Dzen does not provide an official public API; this connector uses the same internal endpoints as the Dzen web app.

## Config

```json
{
  "channel_name": "mychannel",
  "session_id": "<optional Session_id cookie>",
  "csrf_token": "<optional x-csrf-token>",
  "publisher_id": "<optional publisher cabinet id>",
  "start_date": "2024-01-01",
  "max_pages": 20
}
```

## Local run

```bash
cd airbyte-integrations/connectors/source-dzen
poetry install
poetry run source-dzen spec
poetry run source-dzen check --config secrets/config.json
poetry run source-dzen discover --config secrets/config.json
```

## Session credentials

To sync your own publisher stats:

1. Log in to [dzen.ru](https://dzen.ru)
2. Open DevTools → Network
3. Copy `Session_id` from cookies and `x-csrf-token` from request headers
4. Copy `publisherId` from the editor URL

Session tokens expire — refresh them if sync fails with HTTP 403.
