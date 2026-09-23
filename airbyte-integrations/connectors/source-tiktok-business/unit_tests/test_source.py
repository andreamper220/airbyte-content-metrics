import json
from pathlib import Path

import pytest
import requests_mock

from source_tiktok_business.source import SourceTiktokBusiness


CONFIG = {
    "access_token": "test-token",
    "business_id": "biz_123",
    "start_date": "2024-01-01",
}


@pytest.fixture
def source():
    return SourceTiktokBusiness()


def test_check_connection_success(source):
    with requests_mock.Mocker() as m:
        m.get(
            "https://business-api.tiktok.com/open_api/v1.3/business/get/",
            json={"code": 0, "message": "OK", "data": {"business_id": "biz_123", "display_name": "Test"}},
        )
        ok, err = source.check_connection(None, CONFIG)
        assert ok is True
        assert err is None


def test_videos_stream_pagination(source):
    streams = {s.name: s for s in source.streams(CONFIG)}
    videos = streams["videos"]

    page1 = {
        "code": 0,
        "data": {
            "videos": [
                {"item_id": "1", "create_time": 1704067200, "video_views": 100, "caption": "first"},
            ],
            "has_more": True,
            "cursor": 1704067200000,
        },
    }
    page2 = {
        "code": 0,
        "data": {
            "videos": [
                {"item_id": "2", "create_time": 1704153600, "video_views": 500, "caption": "viral"},
            ],
            "has_more": False,
        },
    }

    with requests_mock.Mocker() as m:
        m.get("https://business-api.tiktok.com/open_api/v1.3/business/video/list/", [{"json": page1}, {"json": page2}])
        records = list(videos.read_records(sync_mode=None))
        assert len(records) == 2
        assert records[1]["item_id"] == "2"


def test_spec():
    spec = SourceTiktokBusiness().spec(logger=None)
    assert "access_token" in spec.connectionSpecification["properties"]
    assert "refresh_token" in spec.connectionSpecification["properties"]


def test_video_fields_skip_restricted_insights():
    from source_tiktok_business.streams import VIDEO_FIELDS

    assert "reach" not in VIDEO_FIELDS
    assert "average_time_watched" not in VIDEO_FIELDS
