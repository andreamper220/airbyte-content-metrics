import logging
from typing import Any, List, Mapping, Optional, Tuple

from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams.http.auth import TokenAuthenticator

from .streams import ShortVideos


logger = logging.getLogger("airbyte")


class SourceVk(AbstractSource):
    """VK API — short-form videos from a user or community."""

    def check_connection(self, logger: logging.Logger, config: Mapping[str, Any]) -> Tuple[bool, Optional[Any]]:
        stream = ShortVideos(authenticator=TokenAuthenticator(token=config["access_token"]), config=config)
        response = stream.get_response(offset=0)
        body = response.json()
        if response.status_code == 200 and "error" not in body:
            return True, None
        error = body.get("error", {})
        return False, error.get("error_msg", f"HTTP {response.status_code}")

    def streams(self, config: Mapping[str, Any]) -> List:
        authenticator = TokenAuthenticator(token=config["access_token"])
        return [ShortVideos(authenticator=authenticator, config=config)]
