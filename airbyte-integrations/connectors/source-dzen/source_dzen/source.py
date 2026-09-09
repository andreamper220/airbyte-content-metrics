import logging
from typing import Any, List, Mapping, Optional, Tuple

from airbyte_cdk.sources import AbstractSource

from .streams import Shorts


logger = logging.getLogger("airbyte")


class SourceDzen(AbstractSource):
    """Yandex Dzen — short videos from a public channel feed or publisher API."""

    def check_connection(self, logger: logging.Logger, config: Mapping[str, Any]) -> Tuple[bool, Optional[Any]]:
        stream = Shorts(config=config)
        response = stream.get_response()
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}"
        try:
            payload = response.json()
        except ValueError:
            return False, "Response is not valid JSON"
        if not isinstance(payload, dict):
            return False, "Unexpected API response"
        return True, None

    def streams(self, config: Mapping[str, Any]) -> List:
        return [Shorts(config=config)]
