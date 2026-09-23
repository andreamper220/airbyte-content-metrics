import logging
from typing import Any, List, Mapping, MutableMapping, Optional, Tuple

import requests
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams.http.auth import TokenAuthenticator

from .streams import AccountProfile, Videos


logger = logging.getLogger("airbyte")
REFRESH_URL = "https://business-api.tiktok.com/open_api/v1.3/tt_user/oauth2/refresh_token/"


def refresh_access_token(config: Mapping[str, Any]) -> MutableMapping[str, Any]:
    """Access tokens last 24h; refresh on every run when credentials are present."""
    refreshed: MutableMapping[str, Any] = dict(config)
    refresh_token = config.get("refresh_token")
    app_id = config.get("app_id")
    app_secret = config.get("app_secret")
    if not (refresh_token and app_id and app_secret):
        return refreshed
    response = requests.post(
        REFRESH_URL,
        json={
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    body = response.json()
    data = body.get("data") or {}
    if body.get("code") != 0 or not data.get("access_token"):
        raise RuntimeError(body.get("message") or f"TikTok token refresh failed HTTP {response.status_code}")
    refreshed["access_token"] = data["access_token"]
    if data.get("refresh_token"):
        refreshed["refresh_token"] = data["refresh_token"]
    if data.get("open_id") and not refreshed.get("business_id"):
        refreshed["business_id"] = data["open_id"]
    return refreshed


class SourceTiktokBusiness(AbstractSource):
    """TikTok Business API — organic video and profile analytics."""

    def check_connection(self, logger: logging.Logger, config: Mapping[str, Any]) -> Tuple[bool, Optional[Any]]:
        try:
            config = refresh_access_token(config)
        except Exception as exc:
            return False, str(exc)
        authenticator = TokenAuthenticator(token=config["access_token"])
        stream = AccountProfile(authenticator=authenticator, config=config)
        response = stream.get_response()
        body = response.json()
        if response.status_code == 200 and body.get("code") == 0:
            return True, None
        return False, body.get("message", f"HTTP {response.status_code}")

    def streams(self, config: Mapping[str, Any]) -> List:
        config = refresh_access_token(config)
        authenticator = TokenAuthenticator(token=config["access_token"])
        return [
            AccountProfile(authenticator=authenticator, config=config),
            Videos(authenticator=authenticator, config=config),
        ]
