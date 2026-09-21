from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_database: str = "analytics"

    # Background mart rebuild from ClickHouse raw_* tables
    auto_refresh_enabled: bool = True
    mart_refresh_interval_minutes: int = 15
    auto_refresh_startup_delay_seconds: int = 10

    # Optional: trigger Airbyte connection syncs before mart refresh
    airbyte_sync_enabled: bool = False
    airbyte_sync_interval_minutes: int = 15
    airbyte_api_url: str = ""
    airbyte_username: str = ""
    airbyte_password: str = ""
    airbyte_connection_ids: str = ""

    dzen_channel_name: str = ""

    # Google OAuth (dashboard login)
    google_client_id: str = ""
    google_client_secret: str = ""
    session_secret: str = ""
    oauth_redirect_uri: str = "http://localhost:8080/auth/callback"
    allowed_emails: str = "anrewwolf68@gmail.com,danzobond@gmail.com"

    # Commenting as the owned accounts (YouTube / VK / Dzen)
    comment_credentials_path: str = ""
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_refresh_token: str = ""
    youtube_channel_id: str = ""
    vk_access_token: str = ""
    vk_owner_id: int = 0
    vk_api_version: str = "5.199"
    vk_comment_from_group: bool = True
    vk_config_path: str = ""
    dzen_session_id: str = ""
    dzen_csrf_token: str = ""
    dzen_sess_id: str = ""
    zen_session_id: str = ""
    dzen_cookie: str = ""
    dzen_cookie_path: str = "/secrets/dzen-comment.json"
    dzen_fp_token: str = ""
    youtube_token_path: str = "/secrets/youtube-comment-token.json"


settings = Settings()
