# Created: 2026-07-19
# Last Edited: 2026-08-01 03:18 CT (America/Chicago)
# Path: aetherpod/app.py
# Purpose: Main Textual TUI application — screen orchestration, CSS, playback polling.

from __future__ import annotations

import logging
from pathlib import Path

from textual import events
from textual.app import App
from textual.binding import Binding

from aetherpod import __version__
from aetherpod.engine import DataManager
from aetherpod.player import Player
from aetherpod.screens.episode_screen import EpisodeScreen
from aetherpod.screens.feed_screen import FeedScreen
from aetherpod.screens.now_playing import NowPlayingScreen
from aetherpod.screens.splash import SplashScreen
from aetherpod.theme import THEMES

logger = logging.getLogger(__name__)


class AetherPod(App):
    """Root Textual application for the AetherPod podcast manager.

    Registers custom dark/light themes on mount, pushes the feed subscription
    screen, and runs a 1-second playback poll to keep progress bars live.
    App-level keybinding: ``t`` toggles dark/light theme.
    """

    TITLE = f"AetherPod - v{__version__}"
    SUB_TITLE = ""
    ALLOW_SELECT = False

    BINDINGS = [
        Binding("t", "toggle_theme", "Theme"),
        Binding("space", "global_pause", "Pause"),
    ]

    CSS = """
    Screen {
        background: $surface;
    }

    ListView {
        height: 1fr;
        margin: 0 1;
    }

    ListView > ListItem {
        padding: 0 1;
    }

    ListView > ListItem:hover {
        background: $accent 15%;
    }

    DataTable {
        height: 1fr;
        margin: 0 1;
    }

    DataTable > .datatable--header {
        background: $panel;
        color: $text-muted;
        text-style: bold;
        height: 1;
    }

    DataTable > .datatable--cursor {
        background: $accent 25%;
    }

    .status {
        height: 1;
        background: $panel;
        color: $text-muted;
        padding: 0 1;
    }

    /* ── Dialogs ──────────────────────────────────────── */
    AddFeedDialog, PathInputDialog {
        align: center middle;
        background: $surface 85%;
    }

    AddFeedDialog .dialog-title, PathInputDialog .dialog-title {
        text-style: bold;
        text-align: center;
        width: 100%;
        padding-bottom: 1;
        margin-top: 1;
    }

    AddFeedDialog Input, PathInputDialog Input {
        width: 50;
    }

    AddFeedDialog Button, PathInputDialog Button {
        width: 16;
        margin-top: 1;
    }

    AddFeedDialog .dialog-error, PathInputDialog .dialog-error {
        height: 1;
        text-align: center;
        width: 100%;
    }

    /* ── Now Playing Screen ─────────────────────────────── */
    NowPlayingScreen {
        align: center top;
        background: $surface;
    }

    NowPlayingScreen .np-title {
        text-style: bold;
        text-align: center;
        width: 100%;
        padding-top: 2;
        height: 4;
    }

    NowPlayingScreen .np-progress {
        width: 100%;
        text-align: center;
        height: 2;
    }

    NowPlayingScreen .np-time {
        width: 100%;
        text-align: center;
        height: 2;
    }

    NowPlayingScreen .np-controls {
        width: 100%;
        text-align: center;
        height: 2;
    }

    NowPlayingScreen .np-description {
        width: 70;
        padding: 0 2;
        height: 1fr;
    }

    /* ── Search Screen ──────────────────────────────────── */
    SearchScreen {
        background: $surface;
    }

    SearchScreen Input {
        width: 100%;
        margin: 0 1;
    }

    SearchScreen DataTable {
        height: 1fr;
        margin: 0 1;
    }

    SearchScreen DataTable > .datatable--cursor {
        background: $accent 25%;
    }

    /* ── Episode Detail Screen ──────────────────────────── */
    EpisodeDetailScreen {
        align: center middle;
        background: $surface 90%;
    }

    EpisodeDetailScreen .dialog-title {
        text-style: bold;
        text-align: center;
        width: 100%;
        padding-bottom: 1;
    }

    EpisodeDetailScreen #detail-body {
        width: 70;
        padding: 0 2 1 2;
    }

    EpisodeDetailScreen #detail-footer {
        width: 100%;
        text-align: center;
    }

    /* ── Help Screen ────────────────────────────────────── */
    HelpScreen {
        align: center middle;
        background: $surface 90%;
    }

    HelpScreen .dialog-title {
        text-style: bold;
        text-align: center;
        width: 100%;
        padding-bottom: 1;
    }

    HelpScreen #help-content {
        width: 60;
        padding: 0 2 1 2;
    }

    HelpScreen #help-footer {
        width: 100%;
        text-align: center;
    }

    HelpScreen #help-stack {
        width: 100%;
        text-align: center;
        color: $text-muted;
        padding-bottom: 1;
    }

    /* ── Splash Screen ───────────────────────────────────── */
    SplashScreen {
        align: center middle;
        background: $surface;
    }

    SplashScreen #splash-content {
        width: auto;
        height: auto;
        margin: 1 2;
    }

    SplashScreen #splash-hint {
        dock: bottom;
        width: 100%;
        text-align: center;
        color: $text-muted;
        padding-bottom: 1;
    }

    /* ── Queue Screen ──────────────────────────────────────── */
    QueueScreen {
        background: $surface;
    }

    QueueScreen ListView {
        height: 1fr;
        margin: 0 1;
    }

    QueueScreen ListView > ListItem {
        padding: 0 1;
    }

    QueueScreen ListView > ListItem:hover {
        background: $accent 15%;
    }
    """

    def __init__(self, data_path: str | Path | None = None) -> None:
        super().__init__()
        self._data = DataManager(data_path)
        self._player = Player()

    def on_mount(self) -> None:
        """Register themes, show splash screen, start playback polling."""
        for theme in THEMES.values():
            self.register_theme(theme)
        self.theme = "aetherpod-dark"
        n_feeds = len(self._data.get_feeds())
        n_played = len(self._data.get_played())
        logger.info("AetherPod starting — %d feed(s) loaded", n_feeds)
        self.push_screen(SplashScreen(self._data, self._player, n_feeds, n_played))
        self.set_interval(1, self._poll_playback)

    def on_unmount(self) -> None:
        """Kill mpv when the app exits and clean temp downloads."""
        self._player.stop()
        self._player.cleanup_cache()

    def action_toggle_theme(self) -> None:
        """Toggle between aetherpod-dark and aetherpod-light."""
        self.theme = "aetherpod-light" if self.theme == "aetherpod-dark" else "aetherpod-dark"
        name = self.theme.replace("aetherpod-", "").title()
        self.notify(f"Theme: {name}", severity="information", timeout=1)

    def _poll_playback(self) -> None:
        """1-second poll — update progress + playing indicators."""
        playing_feed = self._player.get_current_feed_url() if self._player.is_playing() else ""
        for screen in self.screen_stack:
            if isinstance(screen, EpisodeScreen):
                screen._update_playback_progress()
            if isinstance(screen, NowPlayingScreen):
                screen._refresh()
            if isinstance(screen, FeedScreen):
                screen._update_playing_indicator(playing_feed)

    def action_global_pause(self) -> None:
        """Toggle pause from any screen (global Space key)."""
        self._player.toggle_pause()
        status = self._player.get_status()
        if status:
            self.notify("Paused" if status.is_paused else "Playing",
                        severity="information", timeout=1)

    def _forward_event(self, event: events.Event) -> None:
        """Work around Textual 8.2.8 crash on Label click during virtual scrolling.

        ``ALLOW_SELECT = False`` should prevent this, but the guard in 8.2.8 is
        not 100% effective — the selection code path is entered regardless of
        ``event.style``.  We swallow the specific AttributeError here.
        """
        try:
            return super()._forward_event(event)
        except AttributeError as exc:
            if "region" in str(exc) and "NoneType" in str(exc):
                logger.debug("Ignored Textual selection bug on %s", type(event).__name__)
            else:
                raise
