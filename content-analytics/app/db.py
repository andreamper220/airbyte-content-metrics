import clickhouse_connect

from app.config import settings


def get_client():
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_database,
    )


def query(sql: str, params: dict | None = None) -> list[dict]:
    client = get_client()
    result = client.query(sql, parameters=params or {})
    columns = result.column_names
    return [dict(zip(columns, row)) for row in result.result_rows]
