# source-tiktok-business

Airbyte source for **TikTok Business organic analytics** (not ads).

## Streams

| Stream | Description |
|--------|-------------|
| `account_profile` | Business account snapshot (followers, video count) |
| `videos` | Organic videos with views, likes, reach, watch time |

## API

Uses [TikTok Business API v1.3](https://business-api.tiktok.com/portal/docs):

- `GET /open_api/v1.3/business/get/`
- `GET /open_api/v1.3/business/video/list/`

## Config

```json
{
  "access_token": "<oauth access token>",
  "business_id": "<business open_id>",
  "start_date": "2024-01-01",
  "max_count": 20
}
```

## Local run

```bash
cd airbyte-integrations/connectors/source-tiktok-business
poetry install
poetry run source-tiktok-business spec
poetry run source-tiktok-business check --config secrets/config.json
poetry run source-tiktok-business discover --config secrets/config.json
```

## OAuth scopes

Your TikTok app needs Business organic scopes (e.g. `biz.brand.insights`, video list permissions per current TikTok developer portal).
