# Created: 2026-07-27
# Last Edited: 2026-07-27 15:54 CT (America/Chicago)
# Path: tests/unit/test_rss.py
# Purpose: Unit tests for RSS fetch helper functions — date parsing, enclosure extraction, bozo messaging.

from __future__ import annotations

from unittest.mock import MagicMock

from aetherpod.rss import _bozo_exception_message, _get_enclosure_url, _parse_feed_date


class TestGetEnclosureUrl:
    def test_returns_audio_enclosure(self) -> None:
        entry = {
            "enclosures": [
                {"href": "https://example.com/ep.mp3", "type": "audio/mpeg"},
            ]
        }
        assert _get_enclosure_url(entry) == "https://example.com/ep.mp3"

    def test_returns_video_enclosure(self) -> None:
        entry = {
            "enclosures": [
                {"href": "https://example.com/ep.mp4", "type": "video/mp4"},
            ]
        }
        assert _get_enclosure_url(entry) == "https://example.com/ep.mp4"

    def test_returns_none_for_no_enclosures(self) -> None:
        assert _get_enclosure_url({}) is None

    def test_skips_non_media_enclosures(self) -> None:
        entry = {
            "enclosures": [
                {"href": "https://example.com/file.pdf", "type": "application/pdf"},
            ]
        }
        assert _get_enclosure_url(entry) is None


class TestParseFeedDate:
    def test_iso_8601(self) -> None:
        dt = _parse_feed_date("2026-07-27T14:00:00+00:00")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 7
        assert dt.day == 27

    def test_rfc_2822(self) -> None:
        dt = _parse_feed_date("Mon, 27 Jul 2026 14:00:00 +0000")
        assert dt is not None

    def test_naive_iso(self) -> None:
        dt = _parse_feed_date("2026-07-27T14:00:00")
        assert dt is not None
        assert dt.tzinfo is not None  # should be made UTC-aware

    def test_none(self) -> None:
        assert _parse_feed_date(None) is None

    def test_garbage(self) -> None:
        assert _parse_feed_date("not-a-date") is None


class TestBozoExceptionMessage:
    def test_none(self) -> None:
        assert _bozo_exception_message(None) == "Unknown parsing error"

    def test_string_exception(self) -> None:
        assert _bozo_exception_message("bad xml") == "bad xml"

    def test_object_with_getMessage(self) -> None:
        exc = MagicMock()
        exc.getMessage.return_value = "SAX parse error"
        assert _bozo_exception_message(exc) == "SAX parse error"
