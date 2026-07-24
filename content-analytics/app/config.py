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
    airbyte_sync_interval_minutes: int = 360
    airbyte_api_url: str = ""
    airbyte_username: str = ""
    airbyte_password: str = ""
    airbyte_connection_ids: str = ""


settings = Settings()
