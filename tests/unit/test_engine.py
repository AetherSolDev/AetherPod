# Created: 2026-07-27
# Last Edited: 2026-07-27 15:54 CT (America/Chicago)
# Path: tests/unit/test_engine.py
# Purpose: Unit tests for DataManager — state persistence, feed/played/progress management.

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from aetherpod.engine import DataManager, Episode, ProgressInfo


@pytest.fixture
def temp_state() -> Path:
    """Create a temporary state file path."""
    return Path(tempfile.mkstemp(suffix=".json")[1])


@pytest.fixture
def dm(temp_state: Path) -> DataManager:
    """Create a DataManager with a temp state file (empty)."""
    return DataManager(temp_state)


class TestDataManager:
    def test_init_creates_empty_state(self, dm: DataManager) -> None:
        assert dm.get_feeds() == []
        assert dm.get_played() == set()

    def test_add_feed(self, dm: DataManager) -> None:
        assert dm.add_feed("https://example.com/feed.xml") is True
        assert dm.get_feeds() == ["https://example.com/feed.xml"]

    def test_add_feed_duplicate(self, dm: DataManager) -> None:
        dm.add_feed("https://example.com/feed.xml")
        assert dm.add_feed("https://example.com/feed.xml") is False
        assert len(dm.get_feeds()) == 1

    def test_remove_feed(self, dm: DataManager) -> None:
        dm.add_feed("https://example.com/feed.xml")
        assert dm.remove_feed("https://example.com/feed.xml") is True
        assert dm.get_feeds() == []
        assert dm.remove_feed("https://example.com/feed.xml") is False

    def test_mark_played(self, dm: DataManager) -> None:
        assert dm.mark_played("ep-001") is True
        assert dm.is_played("ep-001") is True
        assert dm.mark_played("ep-001") is False  # already marked

    def test_unmark_played(self, dm: DataManager) -> None:
        dm.mark_played("ep-001")
        assert dm.unmark_played("ep-001") is True
        assert dm.is_played("ep-001") is False
        assert dm.unmark_played("ep-001") is False

    def test_save_and_get_progress(self, dm: DataManager) -> None:
        dm.save_progress("ep-001", 120.0, 600.0)
        prog = dm.get_progress("ep-001")
        assert prog is not None
        assert prog.position == 120.0
        assert prog.total_length == 600.0

    def test_save_progress_marks_completed(self, dm: DataManager) -> None:
        dm.save_progress("ep-001", 598.0, 600.0)
        assert dm.is_played("ep-001") is True

    def test_get_progress_nonexistent(self, dm: DataManager) -> None:
        assert dm.get_progress("no-such-ep") is None

    def test_persistence_across_reload(self, temp_state: Path) -> None:
        dm1 = DataManager(temp_state)
        dm1.add_feed("https://example.com/feed.xml")
        dm1.mark_played("ep-001")
        dm1.save_progress("ep-001", 100.0, 500.0)

        dm2 = DataManager(temp_state)
        assert dm2.get_feeds() == ["https://example.com/feed.xml"]
        assert dm2.is_played("ep-001") is True
        prog = dm2.get_progress("ep-001")
        assert prog is not None
        assert prog.position == 100.0

    def test_retention_enforced(self, dm: DataManager) -> None:
        for i in range(dm.MAX_PLAYED + 10):
            dm.mark_played(f"ep-{i:03d}")
        assert len(dm.get_played()) <= dm.MAX_PLAYED

    def test_opml_import_no_file(self, dm: DataManager) -> None:
        count = dm.opml_import("/nonexistent/file.opml")
        assert count == 0

    def test_opml_export_empty(self, dm: DataManager) -> None:
        with tempfile.NamedTemporaryFile(suffix=".opml", delete=False) as f:
            path = Path(f.name)
        count = dm.opml_export(str(path))
        assert count == 0
        path.unlink(missing_ok=True)

    def test_load_corrupt_state(self, temp_state: Path) -> None:
        temp_state.write_text("not valid json", encoding="utf-8")
        dm = DataManager(temp_state)
        assert dm.get_feeds() == []
        assert dm.get_played() == set()
