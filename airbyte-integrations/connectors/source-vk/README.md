# source-vk

Airbyte source for **VK short-form videos** (clips and videos up to a configurable duration).

## Streams

| Stream | Description |
|--------|-------------|
| `short_videos` | Short videos from a user or community with views, likes, comments |

## API

Uses [VK API](https://dev.vk.com/ru/method/video.get):

- `GET https://api.vk.com/method/video.get`

Videos are filtered by duration (default ≤ 180 seconds) and optional `type` field.

## Config

```json
{
  "access_token": "<service or user token with video scope>",
  "owner_id": -123456789,
  "start_date": "2024-01-01",
  "max_short_duration_seconds": 180,
  "page_size": 100
}
```

## Local run

```bash
cd airbyte-integrations/connectors/source-vk
poetry install
poetry run source-vk spec
poetry run source-vk check --config secrets/config.json
poetry run source-vk discover --config secrets/config.json
```

## OAuth scopes

Your VK app needs the `video` scope (or manage community videos for group tokens).
