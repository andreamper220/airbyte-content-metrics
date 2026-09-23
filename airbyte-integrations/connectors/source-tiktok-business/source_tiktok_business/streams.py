import json
import logging
from abc import ABC
from pathlib import Path
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional

import pendulum
import requests

from airbyte_cdk.models import SyncMode
from airbyte_cdk.sources.streams.core import IncrementalMixin, StreamData
from airbyte_cdk.sources.streams.http import HttpStream


logger = logging.getLogger("airbyte")
SCHEMAS_PATH = Path(__file__).parent / "schemas"

# Insights like reach / watch time need extra scopes the account-holder
# token usually does not have; requesting them fails the whole page (40130).
VIDEO_FIELDS = [
    "item_id",
    "create_time",
    "caption",
    "share_url",
    "embed_url",
    "thumbnail_url",
    "video_duration",
    "video_views",
    "likes",
    "comments",
    "shares",
]
PROFILE_FIELDS = [
    "username",
    "display_name",
    "profile_image",
    "following_count",
    "videos_count",
    "is_verified",
]


class TiktokBusinessStream(HttpStream, ABC):
    url_base = "https://business-api.tiktok.com/open_api/v1.3/"
    raise_on_http_errors = True

    def __init__(self, config: Mapping[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.business_id = config["business_id"]

    def get_json_schema(self) -> Mapping[str, Any]:
        return json.loads((SCHEMAS_PATH / f"{self.name}.json").read_text(encoding="utf-8"))

    def request_headers(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> Mapping[str, str]:
        return {"Access-Token": self.config["access_token"]}

    def _check_response(self, response: requests.Response) -> None:
        body = response.json()
        if body.get("code") != 0:
            raise requests.HTTPError(
                f"TikTok API error {body.get('code')}: {body.get('message')}",
                response=response,
            )


class AccountProfile(TiktokBusinessStream):
    name = "account_profile"
    primary_key = "business_id"

    def path(self, **kwargs) -> str:
        return "business/get/"

    def request_params(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> MutableMapping[str, Any]:
        return {
            "business_id": self.business_id,
            "fields": json.dumps(PROFILE_FIELDS),
        }

    def parse_response(
        self,
        response: requests.Response,
        stream_state: Mapping[str, Any] = None,
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:
        self._check_response(response)
        data = response.json().get("data", {}) or {}
        if not data:
            return
        data["business_id"] = data.get("business_id") or self.business_id
        if "video_count" not in data and "videos_count" in data:
            data["video_count"] = data.get("videos_count")
        yield data

    def get_response(self) -> requests.Response:
        url = f"{self.url_base}{self.path()}"
        return requests.get(
            url,
            headers=self.request_headers({}),
            params=self.request_params({}),
            timeout=30,
        )


class Videos(TiktokBusinessStream, IncrementalMixin):
    name = "videos"
    cursor_field = "create_time"
    primary_key = "item_id"

    def __init__(self, config: Mapping[str, Any], **kwargs):
        super().__init__(config=config, **kwargs)
        self._cursor_value: Optional[int] = None

    @property
    def state(self) -> Mapping[str, Any]:
        if self._cursor_value is None:
            return {}
        return {self.cursor_field: self._cursor_value}

    @state.setter
    def state(self, value: Mapping[str, Any]) -> None:
        if value and self.cursor_field in value:
            self._cursor_value = int(value[self.cursor_field])

    def path(self, **kwargs) -> str:
        return "business/video/list/"

    def request_params(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> MutableMapping[str, Any]:
        params: MutableMapping[str, Any] = {
            "business_id": self.business_id,
            "fields": json.dumps(VIDEO_FIELDS),
            "max_count": self.config.get("max_count", 20),
        }
        if next_page_token:
            params["cursor"] = next_page_token["cursor"]
        return params

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        self._check_response(response)
        data = response.json().get("data", {})
        if data.get("has_more") and data.get("cursor") is not None:
            return {"cursor": data["cursor"]}
        return None

    def _state_timestamp(self, stream_state: Mapping[str, Any]) -> Optional[int]:
        if stream_state and self.cursor_field in stream_state:
            return int(stream_state[self.cursor_field])
        start_date = self.config.get("start_date")
        if start_date:
            return int(pendulum.parse(start_date).start_of("day").timestamp())
        return None

    def parse_response(
        self,
        response: requests.Response,
        stream_state: Mapping[str, Any] = None,
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:
        self._check_response(response)
        data = response.json().get("data", {})
        videos = data.get("videos") or data.get("list") or []
        cutoff = self._state_timestamp(stream_state or {})

        for video in videos:
            create_time = int(video.get("create_time", 0) or 0)
            if cutoff and create_time < cutoff:
                continue
            video["create_time"] = create_time
            for numeric in (
                "video_views",
                "likes",
                "comments",
                "shares",
                "reach",
                "average_time_watched",
                "total_time_watched",
                "full_video_watched_rate",
                "video_duration",
            ):
                if video.get(numeric) is None:
                    video[numeric] = 0
            if self._cursor_value is None or create_time > self._cursor_value:
                self._cursor_value = create_time
            yield video

    def read_records(
        self,
        sync_mode: SyncMode,
        cursor_field: List[str] = None,
        stream_slice: Mapping[str, Any] = None,
        stream_state: Mapping[str, Any] = None,
    ) -> Iterable[StreamData]:
        yield from super().read_records(sync_mode, cursor_field, stream_slice, stream_state)
