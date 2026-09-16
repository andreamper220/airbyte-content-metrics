import json
import logging
import re
from abc import ABC
from pathlib import Path
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional
from urllib.parse import urlparse

import pendulum
import requests

from airbyte_cdk.models import SyncMode
from airbyte_cdk.sources.streams.core import IncrementalMixin, StreamData
from airbyte_cdk.sources.streams.http import HttpStream


logger = logging.getLogger("airbyte")
SCHEMAS_PATH = Path(__file__).parent / "schemas"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
SHORTS_PATH = re.compile(r"/shorts/([^/?#]+)")


def _first_int(*values: Any) -> int:
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict):
            for key in ("count", "value", "total"):
                if key in value:
                    try:
                        return int(value[key])
                    except (TypeError, ValueError):
                        pass
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _extract_link(item: Mapping[str, Any]) -> str:
    for key in ("link", "url", "shareLink", "publicationUrl", "canonicalUrl"):
        value = item.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    return ""


def _is_short_item(item: Mapping[str, Any]) -> bool:
    link = _extract_link(item)
    if "/shorts/" in link:
        return True
    for key in ("type", "contentType", "cardType", "publicationType"):
        value = str(item.get(key) or "").lower()
        if "short" in value:
            return True
        if value in {"gif", "video", "short_video", "vertical_video"}:
            return True
    # Channel feed cards (e.g. generator_video) often omit /shorts/ in API payloads.
    if link and "dzen.ru" in link and _extract_title(item):
        return True
    return False


def _extract_publication_id(item: Mapping[str, Any], link: str) -> str:
    for key in ("publicationId", "publication_id", "id", "itemId", "contentId"):
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    match = SHORTS_PATH.search(link)
    if match:
        return match.group(1)
    return ""


def _extract_published_at(item: Mapping[str, Any]) -> int:
    for key in ("published_at", "publishTime", "publicationDate", "publishDate", "date", "createdAt"):
        value = item.get(key)
        if value is None:
            continue
        if isinstance(value, (int, float)):
            timestamp = int(value)
            if timestamp > 10_000_000_000:
                timestamp //= 1000
            return timestamp
        if isinstance(value, str) and value.strip():
            try:
                return int(pendulum.parse(value).timestamp())
            except (ValueError, TypeError):
                continue
    return 0


def _extract_title(item: Mapping[str, Any]) -> str:
    for key in ("title", "name", "snippet", "text"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_metrics(item: Mapping[str, Any]) -> tuple[int, int, int]:
    stats = item.get("statistics") or item.get("stats") or item.get("socialInfo") or {}
    if not isinstance(stats, dict):
        stats = {}
    views = _first_int(item.get("views"), stats.get("views"), stats.get("viewCount"), item.get("viewCount"))
    likes = _first_int(item.get("likes"), stats.get("likes"), stats.get("likeCount"), item.get("likeCount"))
    comments = _first_int(item.get("comments"), stats.get("comments"), stats.get("commentCount"), item.get("commentCount"))
    return views, likes, comments


def _walk_publication_nodes(payload: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(payload, list):
        for entry in payload:
            yield from _walk_publication_nodes(entry)
        return
    if not isinstance(payload, dict):
        return

    link = _extract_link(payload)
    publication_id = _extract_publication_id(payload, link)
    if link or publication_id:
        yield payload

    for key in ("items", "publications", "entries", "cards", "feed", "data", "result"):
        if key in payload:
            yield from _walk_publication_nodes(payload[key])


def _normalize_short(item: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    if not _is_short_item(item):
        return None
    link = _extract_link(item)
    publication_id = _extract_publication_id(item, link)
    if not publication_id and not link:
        return None
    if not link and publication_id:
        link = f"https://dzen.ru/shorts/{publication_id}"
    if not publication_id and link:
        publication_id = _extract_publication_id({}, link)
    views, likes, comments = _extract_metrics(item)
    return {
        "publication_id": publication_id,
        "title": _extract_title(item),
        "published_at": _extract_published_at(item),
        "url": link,
        "views": views,
        "likes": likes,
        "comments": comments,
        "content_type": "short",
    }


class DzenStream(HttpStream, ABC):
    url_base = "https://dzen.ru/"
    http_method = "GET"
    raise_on_http_errors = True

    def __init__(self, config: Mapping[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.channel_name = config["channel_name"].strip().lstrip("@")
        self.max_pages = int(config.get("max_pages", 20))

    def get_json_schema(self) -> Mapping[str, Any]:
        return json.loads((SCHEMAS_PATH / f"{self.name}.json").read_text(encoding="utf-8"))

    def request_headers(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> Mapping[str, str]:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        csrf_token = self.config.get("csrf_token")
        if csrf_token:
            headers["x-csrf-token"] = csrf_token
        return headers

    def _session_cookies(self) -> Mapping[str, str]:
        session_id = self.config.get("session_id")
        if not session_id:
            return {}
        return {"Session_id": session_id}


class Shorts(DzenStream, IncrementalMixin):
    name = "shorts"
    cursor_field = "published_at"
    primary_key = "publication_id"

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
        return "api/v3/launcher/more"

    def request_params(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> MutableMapping[str, Any]:
        if next_page_token and next_page_token.get("url"):
            parsed = urlparse(next_page_token["url"])
            if parsed.query:
                return dict(x.split("=", 1) for x in parsed.query.split("&") if "=" in x)
        return {
            "channel_name": self.channel_name,
            "country_code": "ru",
        }

    def request_url(
        self,
        stream_state: Mapping[str, Any],
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> str:
        if next_page_token and next_page_token.get("url"):
            return next_page_token["url"]
        return f"{self.url_base}{self.path()}"

    def next_page_token(self, response: requests.Response) -> Optional[Mapping[str, Any]]:
        try:
            payload = response.json()
        except ValueError:
            return None
        more = payload.get("more") or {}
        link = more.get("link") if isinstance(more, dict) else None
        if isinstance(link, str) and link.startswith("http"):
            page = int(response.request.headers.get("X-Dzen-Page", "0")) + 1
            if page >= self.max_pages:
                return None
            return {"url": link, "page": page}
        return None

    def _start_timestamp(self, stream_state: Mapping[str, Any]) -> Optional[int]:
        if stream_state and self.cursor_field in stream_state:
            return int(stream_state[self.cursor_field])
        start_date = self.config.get("start_date")
        if start_date:
            return int(pendulum.parse(start_date).start_of("day").timestamp())
        return None

    def _records_from_payload(self, payload: Mapping[str, Any], cutoff: Optional[int]) -> Iterable[Mapping[str, Any]]:
        seen: set[str] = set()
        for node in _walk_publication_nodes(payload):
            record = _normalize_short(node)
            if not record:
                continue
            publication_id = record["publication_id"]
            if not publication_id or publication_id in seen:
                continue
            seen.add(publication_id)
            published_at = record["published_at"]
            if cutoff and published_at and published_at < cutoff:
                continue
            if published_at and (self._cursor_value is None or published_at > self._cursor_value):
                self._cursor_value = published_at
            yield record

    def parse_response(
        self,
        response: requests.Response,
        stream_state: Mapping[str, Any] = None,
        stream_slice: Mapping[str, Any] = None,
        next_page_token: Mapping[str, Any] = None,
    ) -> Iterable[Mapping[str, Any]]:
        payload = response.json()
        cutoff = self._start_timestamp(stream_state or {})
        yield from self._records_from_payload(payload, cutoff)

    def _fetch_publisher_shorts(self, cutoff: Optional[int]) -> Iterable[Mapping[str, Any]]:
        publisher_id = self.config.get("publisher_id")
        session_id = self.config.get("session_id")
        if not publisher_id or not session_id:
            return

        url = f"https://dzen.ru/editor-api/v2/publications"
        params = {
            "publisherId": publisher_id,
            "page": 0,
            "pageSize": 100,
            "sortType": "publishTime",
            "sortOrder": "desc",
        }
        headers = dict(self.request_headers({}))
        response = requests.get(
            url,
            params=params,
            headers=headers,
            cookies=self._session_cookies(),
            timeout=30,
        )
        if response.status_code != 200:
            logger.warning("Dzen publisher API returned HTTP %s", response.status_code)
            return
        try:
            payload = response.json()
        except ValueError:
            return
        yield from self._records_from_payload(payload, cutoff)

    def get_response(self) -> requests.Response:
        url = f"{self.url_base}{self.path()}"
        return requests.get(
            url,
            params=self.request_params({}),
            headers=self.request_headers({}),
            cookies=self._session_cookies(),
            timeout=30,
        )

    def _fetch_export_feed(self, cutoff: Optional[int]) -> Iterable[Mapping[str, Any]]:
        url = f"{self.url_base}api/v3/launcher/export"
        response = requests.get(
            url,
            params={"channel_name": self.channel_name, "country_code": "ru"},
            headers=self.request_headers({}),
            cookies=self._session_cookies(),
            timeout=30,
        )
        if response.status_code != 200:
            logger.warning("Dzen export feed returned HTTP %s", response.status_code)
            return
        try:
            payload = response.json()
        except ValueError:
            return
        yield from self._records_from_payload(payload, cutoff)

    def read_records(
        self,
        sync_mode: SyncMode,
        cursor_field: List[str] = None,
        stream_slice: Mapping[str, Any] = None,
        stream_state: Mapping[str, Any] = None,
    ) -> Iterable[StreamData]:
        cutoff = self._start_timestamp(stream_state or {})
        seen_ids: set[str] = set()

        for record in self._fetch_export_feed(cutoff):
            seen_ids.add(record["publication_id"])
            yield StreamData(record=record, associated_slice=stream_slice or {})

        for record in self._fetch_publisher_shorts(cutoff):
            seen_ids.add(record["publication_id"])
            yield StreamData(record=record, associated_slice=stream_slice or {})

        page = 0
        next_token: Optional[Mapping[str, Any]] = None
        while page < self.max_pages:
            url = self.request_url(stream_state or {}, next_page_token=next_token)
            headers = dict(self.request_headers({}))
            headers["X-Dzen-Page"] = str(page)
            response = requests.get(
                url,
                headers=headers,
                cookies=self._session_cookies(),
                timeout=30,
            )
            response.raise_for_status()
            for record in self.parse_response(response, stream_state):
                if record["publication_id"] in seen_ids:
                    continue
                seen_ids.add(record["publication_id"])
                yield StreamData(record=record, associated_slice=stream_slice or {})
            next_token = self.next_page_token(response)
            if not next_token:
                break
            page += 1
