# Created: 2026-08-05
# Last Edited: 2026-08-05 14:45 CT (America/Chicago)
# Path: tests/unit/test_feed_screen.py
# Purpose: Regression tests for FeedScreen ListView selection races (stale click).

from __future__ import annotations

from unittest.mock import MagicMock

from textual._context import active_app

from aetherpod.screens.episode_screen import EpisodeScreen
from aetherpod.screens.feed_screen import FeedScreen


class _FakeApp:
    """Minimal app stand-in that records push_screen calls."""

    def __init__(self) -> None:
        self.screens: list[object] = []
        self._app = self

    @property
    def _parent(self) -> None:
        """Terminate MessagePump.app parent traversal (this fake is the root)."""
        return None

    def push_screen(self, screen: object, *args, **kwargs) -> None:
        self.screens.append(screen)


def _make_screen() -> FeedScreen:
    """Build a FeedScreen with mocked data/player and a fake app."""
    screen = FeedScreen(MagicMock(), MagicMock())
    token = active_app.set(_FakeApp())
    try:
        yield screen
    finally:
        active_app.reset(token)


def test_stale_list_item_selection_ignored() -> None:
    """A Selected event whose item is no longer in the ListView must not crash."""
    for screen in _make_screen():
        feed_list = MagicMock()
        feed_list._nodes = []  # the item below was replaced by a background refresh
        screen.query_one = MagicMock(return_value=feed_list)

        event = MagicMock()
        event.item = MagicMock(_feed_url="https://old.example/rss")

        # Must not raise ValueError: list.index(x): x not in list
        screen.on_list_view_selected(event)


def test_live_list_item_selection_browses_feed() -> None:
    """A Selected event whose item is still in the ListView pushes EpisodeScreen."""
    for screen in _make_screen():
        item = MagicMock(_feed_url="https://feed.example/rss", _feed_result=MagicMock(error=None))
        item._feed_result.episodes = [MagicMock()]

        feed_list = MagicMock()
        feed_list._nodes = [item]
        screen.query_one = MagicMock(return_value=feed_list)

        screen.on_list_view_selected(MagicMock(item=item))

        assert screen.app.screens and isinstance(screen.app.screens[0], EpisodeScreen)
