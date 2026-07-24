import logging
from pathlib import Path
from typing import Any, List, Mapping, Optional, Tuple

from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams.http.auth import TokenAuthenticator

from .streams import AccountProfile, Videos


logger = logging.getLogger("airbyte")


class SourceTiktokBusiness(AbstractSource):
    """TikTok Business API — organic video and profile analytics."""

    def check_connection(self, logger: logging.Logger, config: Mapping[str, Any]) -> Tuple[bool, Optional[Any]]:
        authenticator = TokenAuthenticator(token=config["access_token"])
        stream = AccountProfile(authenticator=authenticator, config=config)
        response = stream.get_response()
        body = response.json()
        if response.status_code == 200 and body.get("code") == 0:
            return True, None
        return False, body.get("message", f"HTTP {response.status_code}")

    def streams(self, config: Mapping[str, Any]) -> List:
        authenticator = TokenAuthenticator(token=config["access_token"])
        return [
            AccountProfile(authenticator=authenticator, config=config),
            Videos(authenticator=authenticator, config=config),
        ]
