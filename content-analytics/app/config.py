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

    # Google OAuth (dashboard login)
    google_client_id: str = ""
    google_client_secret: str = ""
    session_secret: str = ""
    oauth_redirect_uri: str = "http://localhost:8080/auth/callback"
    allowed_emails: str = "anrewwolf68@gmail.com,danzobond@gmail.com"


settings = Settings()
