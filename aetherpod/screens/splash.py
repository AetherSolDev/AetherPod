# Created: 2026-07-27
# Last Edited: 2026-07-27 15:54 CT (America/Chicago)
# Path: aetherpod/screens/splash.py
# Purpose: Startup splash screen — auto-dismisses after 4s or any key.

from __future__ import annotations

import shutil

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Label, Static

from aetherpod.engine import DataManager
from aetherpod.player import Player
from aetherpod.splash import SplashRenderable


class SplashScreen(Screen):
    BINDINGS = [
        Binding("any", "dismiss", "Skip"),
    ]

    def __init__(
        self, data_manager: DataManager, player: Player, n_feeds: int, n_played: int
    ) -> None:
        super().__init__()
        self._data = data_manager
        self._player = player
        self._n_feeds = n_feeds
        self._n_played = n_played
        self._timer = None

    def compose(self) -> ComposeResult:
        mpv_ok = shutil.which("mpv") is not None
        splash = SplashRenderable(self._n_feeds, self._n_played, mpv_ok)
        yield Static(splash, id="splash-content")
        yield Label("  Press any key or wait\u2026  ", id="splash-hint")

    def on_mount(self) -> None:
        self.title = ""
        self._timer = self.set_timer(4, self._auto_dismiss)

    def action_dismiss(self) -> None:
        if self._timer is not None:
            self._timer.reset()
            self._timer = None
        self.app.pop_screen()
        from aetherpod.screens.feed_screen import FeedScreen
        self.app.push_screen(FeedScreen(self._data, self._player))

    def _auto_dismiss(self) -> None:
        self._timer = None
        self.action_dismiss()
