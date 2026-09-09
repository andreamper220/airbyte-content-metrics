from typing import Any

from app.db import get_client, query

DEFAULT_UTM_MAP = [
    {"platform": "youtube", "utm_source": "youtube"},
    {"platform": "tiktok", "utm_source": "tiktok"},
    {"platform": "tiktok", "utm_source": "tt"},
    {"platform": "instagram", "utm_source": "instagram"},
    {"platform": "instagram", "utm_source": "ig"},
    {"platform": "vk", "utm_source": "vk"},
    {"platform": "vk", "utm_source": "vkontakte"},
    {"platform": "dzen", "utm_source": "dzen"},
    {"platform": "dzen", "utm_source": "zen"},
    {"platform": "dzen", "utm_source": "yandex_zen"},
]

PLATFORMS = ["youtube", "tiktok", "instagram", "vk", "dzen"]


def get_utm_mapping() -> list[dict[str, str]]:
    rows = query(
        """
        SELECT platform, utm_source
        FROM analytics.platform_utm_mapping FINAL
        ORDER BY platform, utm_source
        """
    )
    if not rows:
        save_utm_mapping(DEFAULT_UTM_MAP)
        return DEFAULT_UTM_MAP.copy()
    return rows


def save_utm_mapping(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        platform = str(row.get("platform", "")).strip().lower()
        utm_source = str(row.get("utm_source", "")).strip().lower()
        if not platform or not utm_source:
            continue
        if platform not in PLATFORMS:
            continue
        key = (platform, utm_source)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append({"platform": platform, "utm_source": utm_source})

    if not cleaned:
        cleaned = DEFAULT_UTM_MAP.copy()

    client = get_client()
    client.command("TRUNCATE TABLE analytics.platform_utm_mapping")
    client.insert(
        "platform_utm_mapping",
        [(row["platform"], row["utm_source"]) for row in cleaned],
        column_names=["platform", "utm_source"],
    )
    return cleaned
