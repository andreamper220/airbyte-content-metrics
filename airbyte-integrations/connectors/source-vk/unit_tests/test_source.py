import json
from pathlib import Path

import pytest
import requests_mock

from source_vk.source import SourceVk


CONFIG = {
    "access_token": "test-token",
    "owner_id": -123456789,
    "start_date": "2024-01-01",
    "max_short_duration_seconds": 180,
}


@pytest.fixture
def source():
    return SourceVk()


def test_check_connection_success(source):
    with requests_mock.Mocker() as m:
        m.get(
            "https://api.vk.com/method/video.get",
            json={"response": {"count": 1, "items": [{"id": 1, "owner_id": -123456789, "date": 1704067200, "duration": 45}]}},
        )
        ok, err = source.check_connection(None, CONFIG)
        assert ok is True
        assert err is None


def test_short_videos_stream_filters_long_videos(source):
    streams = {s.name: s for s in source.streams(CONFIG)}
    short_videos = streams["short_videos"]

    response_body = {
        "response": {
            "count": 2,
            "items": [
                {
                    "id": 1,
                    "owner_id": -123456789,
                    "date": 1704067200,
                    "duration": 45,
                    "title": "clip",
                    "views": 100,
                    "likes": {"count": 10},
                    "reposts": {"count": 2},
                    "comments": 1,
                },
                {
                    "id": 2,
                    "owner_id": -123456789,
                    "date": 1704153600,
                    "duration": 600,
                    "title": "long video",
                    "views": 500,
                    "likes": {"count": 50},
                    "reposts": {"count": 0},
                    "comments": 0,
                },
            ],
        }
    }

    with requests_mock.Mocker() as m:
        m.get("https://api.vk.com/method/video.get", json=response_body)
        m.get("https://api.vk.com/method/wall.get", json={"response": {"count": 0, "items": []}})
        records = list(short_videos.read_records(sync_mode=None))
        assert len(records) == 1
        assert records[0]["video_id"] == "-123456789_1"
        assert records[0]["views"] == 100


def test_short_videos_falls_back_to_wall_when_video_get_unauthorized(source):
    streams = {s.name: s for s in source.streams(CONFIG)}
    short_videos = streams["short_videos"]
    wall_body = {
        "response": {
            "count": 1,
            "items": [
                {
                    "attachments": [
                        {
                            "type": "video",
                            "video": {
                                "id": 99,
                                "owner_id": -123456789,
                                "date": 1704067200,
                                "duration": 30,
                                "title": "wall clip",
                                "views": 50,
                                "likes": {"count": 3},
                                "reposts": {"count": 0},
                                "comments": 0,
                            },
                        }
                    ]
                }
            ],
        }
    }
    with requests_mock.Mocker() as m:
        m.get(
            "https://api.vk.com/method/video.get",
            json={"error": {"error_code": 5, "error_msg": "User authorization failed"}},
        )
        m.get("https://api.vk.com/method/wall.get", json=wall_body)
        records = list(short_videos.read_records(sync_mode=None))
        assert len(records) == 1
        assert records[0]["video_id"] == "-123456789_99"


def test_spec():
    spec = SourceVk().spec(logger=None)
    assert "access_token" in spec.connectionSpecification["properties"]
