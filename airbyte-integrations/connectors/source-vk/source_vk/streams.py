import json
import logging
from abc import ABC
from pathlib import Path
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional
from urllib.parse import parse_qs, urlparse

import pendulum
import requests

from airbyte_cdk.models import SyncMode
from airbyte_cdk.sources.streams.core import IncrementalMixin, StreamData
from airbyte_cdk.sources.streams.http import HttpStream


logger = logging.getLogger("airbyte")
SCHEMAS_PATH = Path(__file__).parent / "schemas"


class VkStream(HttpStream, ABC):
    url_base = "https://api.vk.com/method/"
    http_method = "GET"
    raise_on_http_errors = True

    def __init__(self, config: Mapping[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.owner_id = int(config["owner_id"])
        self.api_version = config.get("api_version", "5.199")

    def get_json_schema(self) -> Mapping[str, Any]:
        return json.loads((SCHEMAS_PATH / f"{self.name}.json").read_text(encoding="utf-8"))

    def _check_response(self, response: requests.Response) -> None:
        body = response.json()
        error = body.get("error")
        if error:
            raise requests.HTTPError(
                f"VK API error {error.get('error_code')}: {error.get('error_msg')}",
                response=response,
            )


class ShortVideos(VkStream, IncrementalMixin):
    name = "short_videos"
    cursor_field = "published_at"
    primary_key = "video_id"

    def __init__(self, config: Mapping[str, Any], **kwargs):
        super().__init__(config=config, **kwargs)
        self._cursor_value: Optional[int] = None
        self.max_duration = int(config.get("max_short_duration_seconds", 180))
        self.page_size = int(config.get("page_size", 100))

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
        return "video.get"

    def request_params(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> MutableMapping[str, Any]:
        offset = 0
        if next_page_token:
            offset = int(next_page_token["offset"])
        return {
            "owner_id": self.owner_id,
            "count": self.page_size,
            "offset": offset,
            "extended": 0,
            "access_token": self.config["access_token"],
            "v": self.api_version,
        }

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        self._check_response(response)
        parsed = urlparse(response.url)
        query = parse_qs(parsed.query)
        current_offset = int(query.get("offset", ["0"])[0])
        data = response.json().get("response", {})
        items = data.get("items") or []
        total = int(data.get("count") or 0)
        next_offset = current_offset + len(items)
        if next_offset < total and items:
            return {"offset": next_offset}
        return None

    def _start_timestamp(self, stream_state: Mapping[str, Any]) -> Optional[int]:
        if stream_state and self.cursor_field in stream_state:
            return int(stream_state[self.cursor_field])
        start_date = self.config.get("start_date")
        if start_date:
            return int(pendulum.parse(start_date).start_of("day").timestamp())
        return None

    def _is_short_video(self, video: Mapping[str, Any]) -> bool:
        duration = int(video.get("duration") or 0)
        if duration <= 0 or duration <= self.max_duration:
            return True
        video_type = str(video.get("type") or "").lower()
        return video_type in {"short_video", "clip", "short"}

    def _normalize_video(self, video: Mapping[str, Any]) -> Mapping[str, Any]:
        owner_id = int(video.get("owner_id", self.owner_id))
        video_numeric_id = int(video["id"])
        likes = video.get("likes") or {}
        reposts = video.get("reposts") or {}
        published_at = int(video.get("date") or 0)
        return {
            "video_id": f"{owner_id}_{video_numeric_id}",
            "owner_id": owner_id,
            "title": video.get("title") or "",
            "description": video.get("description") or "",
            "published_at": published_at,
            "duration": int(video.get("duration") or 0),
            "views": int(video.get("views") or 0),
            "likes": int(likes.get("count") or 0) if isinstance(likes, dict) else int(likes or 0),
            "comments": int(video.get("comments") or 0),
            "reposts": int(reposts.get("count") or 0) if isinstance(reposts, dict) else int(reposts or 0),
            "player_url": video.get("player") or "",
            "share_url": f"https://vk.com/video{owner_id}_{video_numeric_id}",
        }

    def parse_response(
        self,
        response: requests.Response,
        stream_state: Mapping[str, Any] = None,
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:
        self._check_response(response)
        items = response.json().get("response", {}).get("items") or []
        cutoff = self._start_timestamp(stream_state or {})

        for video in items:
            if not self._is_short_video(video):
                continue
            record = self._normalize_video(video)
            published_at = record["published_at"]
            if cutoff and published_at < cutoff:
                continue
            if self._cursor_value is None or published_at > self._cursor_value:
                self._cursor_value = published_at
            yield record

    def get_response(self, offset: int = 0) -> requests.Response:
        url = f"{self.url_base}{self.path()}"
        params = self.request_params({}, next_page_token={"offset": offset})
        return requests.get(url, params=params, timeout=30)

    def read_records(
        self,
        sync_mode: SyncMode,
        cursor_field: List[str] = None,
        stream_slice: Mapping[str, Any] = None,
        stream_state: Mapping[str, Any] = None,
    ) -> Iterable[StreamData]:
        yield from super().read_records(sync_mode, cursor_field, stream_slice, stream_state)
