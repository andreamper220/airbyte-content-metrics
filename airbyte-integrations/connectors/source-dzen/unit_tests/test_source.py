import pytest
import requests_mock

from source_dzen.source import SourceDzen


CONFIG = {
    "channel_name": "demo_channel",
    "start_date": "2024-01-01",
}


@pytest.fixture
def source():
    return SourceDzen()


def test_check_connection_success(source):
    with requests_mock.Mocker() as m:
        m.get(
            "https://dzen.ru/api/v3/launcher/more",
            json={"items": [], "more": {}},
        )
        ok, err = source.check_connection(None, CONFIG)
        assert ok is True
        assert err is None


def test_shorts_stream_parses_short_items(source):
    streams = {s.name: s for s in source.streams(CONFIG)}
    shorts = streams["shorts"]

    payload = {
        "items": [
            {
                "type": "card",
                "link": "https://dzen.ru/shorts/abc123",
                "title": "Short clip",
                "views": 1500,
                "likes": 120,
                "comments": 8,
                "publishTime": 1704067200,
            },
            {
                "type": "card",
                "link": "https://dzen.ru/a/article123",
                "title": "Article",
                "views": 9000,
                "publishTime": 1704153600,
            },
        ],
        "more": {},
    }

    with requests_mock.Mocker() as m:
        m.get("https://dzen.ru/api/v3/launcher/export", json={"items": []})
        m.get("https://dzen.ru/api/v3/launcher/more", json=payload)
        records = list(shorts.read_records(sync_mode=None))
        assert len(records) == 1
        assert records[0]["publication_id"] == "abc123"
        assert records[0]["views"] == 1500


def test_shorts_stream_walks_nested_block_items(source):
    streams = {s.name: s for s in source.streams(CONFIG)}
    shorts = streams["shorts"]
    payload = {
        "items": [
            {
                "item_type": "channel_block_shorts",
                "type": "generator_video",
                "title": "Ролики",
                "items": [
                    {
                        "type": "short_video",
                        "publication_object_id": "gif:6aad106f1f92461355f2e655",
                        "title": "AI-АВАТАР ЗАБИРАЕТ ТРЕНДЫ",
                        "link": "https://dzen.ru/video/watch/6aad106f1f92461355f2e655",
                        "views": 1200,
                    }
                ],
            }
        ]
    }
    with requests_mock.Mocker() as m:
        m.get("https://dzen.ru/api/v3/launcher/export", json=payload)
        m.get("https://dzen.ru/api/v3/launcher/more", json={"items": [], "more": {}})
        records = list(shorts.read_records(sync_mode=None))
        assert len(records) == 1
        assert records[0]["publication_id"] == "6aad106f1f92461355f2e655"
        assert records[0]["published_at"] == int("6aad106f", 16)


def test_spec():
    spec = SourceDzen().spec(logger=None)
    assert "channel_name" in spec.connectionSpecification["properties"]
