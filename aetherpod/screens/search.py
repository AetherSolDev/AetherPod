# Created: 2026-07-27
# Last Edited: 2026-08-01 11:41 CT (America/Chicago)
# Path: aetherpod/screens/search.py
# Purpose: Cross-feed episode search screen — live filter by title.

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Static

from aetherpod.engine import DataManager
from aetherpod.models import Episode
from aetherpod.player import Player
from aetherpod.screens.helpers import format_date


class SearchScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]

    def __init__(self, data_manager: DataManager, player: Player) -> None:
        super().__init__()
        self._data = data_manager
        self._player = player
        self._all_episodes: list[Episode] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Search episodes\u2026", id="search-input")
        yield Static(
            "Type to search \u2014 Enter to play selected result",
            id="search-status", classes="status",
        )
        yield DataTable(id="search-results")
        yield Footer()

    def on_mount(self) -> None:
        for url in self._data.get_feeds():
            cached = self._data.get_cached_result(url)
            if cached and cached.episodes:
                self._all_episodes.extend(cached.episodes)
        self.query_one(Input).focus()

        table = self.query_one("#search-results", DataTable)
        table.add_column("Feed", width=20)
        table.add_column("Title", width=50)
        table.add_column("Date", width=12)
        table.cursor_type = "row"
        table.zebra_stripes = True

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.strip().lower()
        table = self.query_one("#search-results", DataTable)
        table.clear()
        if not query:
            return

        for ep in self._all_episodes:
            if query in ep.title.lower():
                feed_title = ""
                for url in self._data.get_feeds():
                    cached = self._data.get_cached_result(url)
                    if cached and any(e.episode_id == ep.episode_id for e in cached.episodes):
                        feed_title = cached.title
                        break
                title_trunc = (ep.title[:47] + "\u2026") if len(ep.title) > 47 else ep.title
                table.add_row(
                    Text(feed_title, style="dim"),
                    Text(title_trunc, style="bold"),
                    Text(format_date(ep.published), style="dim"),
                )

    def _find_episode_by_title(self, title: str) -> Episode | None:
        for ep in self._all_episodes:
            if ep.title == title:
                return ep
        return None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = event.row_key
        table = self.query_one("#search-results", DataTable)
        row = table.get_row(row_key)
        if not row or len(row) < 2:
            return
        feed_title = row[0].plain if hasattr(row[0], 'plain') else str(row[0])
        for ep in self._all_episodes:
            for url in self._data.get_feeds():
                cached = self._data.get_cached_result(url)
                if cached and cached.title == feed_title and ep.episode_id:
                    if any(e.episode_id == ep.episode_id for e in cached.episodes):
                        self._play_episode(ep)
                        return

    def _play_episode(self, episode: Episode) -> None:
        if not episode.url:
            self.notify("No audio URL", severity="warning", timeout=3)
            return
        if self._player.is_playing():
            self._player.stop()
        epid = episode.episode_id or ""
        start_pos: float | None = None
        if not self._data.is_played(epid):
            prog = self._data.get_progress(epid)
            if prog and prog.total_length > 0 and 0 < prog.position < prog.total_length - 5:
                start_pos = prog.position

        def _on_progress(eid: str, pos: float, total: float) -> None:
            self._data.save_progress(eid, pos, total)

        err = self._player.play(episode.url, epid, _on_progress, start_pos=start_pos)
        if err:
            self.notify(f"Playback failed: {err}", severity="error", timeout=5)
        else:
            self.notify(f"\u25b6 {episode.title}", severity="information", timeout=3)
            self.app.pop_screen()

    def action_dismiss(self) -> None:
        self.app.pop_screen()
