# Created: 2026-07-19
# Last Edited: 2026-08-01 03:13 CT (America/Chicago)
# Path: aetherpod/screens/episode_screen.py
# Purpose: Episode browser for a single feed — play, filter, sort, scrub, queue.

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual import events
from textual.message import Message
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from rich.text import Text

from aetherpod.engine import DataManager
from aetherpod.engines import PlayerStatus
from aetherpod.models import Episode, FeedResult
from aetherpod.player import Player
from aetherpod.rss import fetch_feed_async
from aetherpod.screens.detail_help import EpisodeDetailScreen, HelpScreen
from aetherpod.screens.helpers import format_date
from aetherpod.screens.now_playing import NowPlayingScreen
from aetherpod.screens.queue import QueueScreen
from aetherpod.widgets import LoadingSpinner

logger = logging.getLogger(__name__)


class PlaybackStateChanged(Message):
    """Posted when playback state (playing/paused/stopped) changes."""


class EpisodeScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("u", "refresh", "Refresh"),
        Binding("enter", "play", "Play", priority=True),
        Binding("space", "pause", "Pause"),
        Binding("s", "stop", "Stop"),
        Binding("left_bracket", "speed_down", "Slower", key_display="["),
        Binding("right_bracket", "speed_up", "Faster", key_display="]"),
        Binding("left", "seek_back", "Seek -30s"),
        Binding("right", "seek_forward", "Seek +30s"),
        Binding("f", "toggle_filter", "Filter"),
        Binding("ctrl+left", "seek_fine_back", "Seek -1s"),
        Binding("ctrl+right", "seek_fine_forward", "Seek +1s"),
        Binding("period", "toggle_scrub", "Scrub"),
        Binding("d", "show_details", "Details"),
        Binding("n", "now_playing", "Now Playing"),
        Binding("m", "toggle_played", "Mark"),
        Binding("1", "eq_off", "EQ:Off", key_display="1"),
        Binding("2", "eq_bright", "EQ:Bright", key_display="2"),
        Binding("3", "eq_warm", "EQ:Warm", key_display="3"),
        Binding("4", "eq_balanced", "EQ:Balanced", key_display="4"),
        Binding("r", "restart", "Restart"),
        Binding("a", "add_to_queue", "Queue"),
        Binding("shift+a", "play_next", "Play Next", key_display="A"),
        Binding("q", "quit", "Quit"),
        Binding("v", "view_queue", "Queue"),
        Binding("question_mark", "show_help", "Help", key_display="?"),
    ]

    def __init__(
        self,
        feed_result: FeedResult,
        feed_url: str | None,
        data_manager: DataManager,
        player: Player,
    ) -> None:
        super().__init__()
        self._feed = feed_result
        self._feed_url = feed_url or feed_result.title
        self._data = data_manager
        self._player = player
        self._show_unplayed_only = False
        self._player_status: PlayerStatus | None = None
        self._title_width: int = 42
        self._sort_column: str = "Date"
        self._sort_state: int = 0
        self._row_keys: dict[str, str] = {}
        self._episodes_by_row: dict[str, Episode] = {}
        self._scrub_mode: bool = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield LoadingSpinner(id="ep-status")
        yield DataTable(id="episode-list")
        yield Footer()

    async def on_mount(self) -> None:
        if self._player.is_process_alive():
            status = self._player.get_status()
            if status is None:
                live_pos, live_len = self._player.get_live_progress()
                if live_pos > 0:
                    status = PlayerStatus(is_playing=True, is_paused=False,
                                          position=live_pos, duration=live_len)
            self._player_status = status

        table = self.query_one("#episode-list", DataTable)
        table.add_column("Status", width=8)
        table.add_column("Title", width=self._title_width)
        table.add_column("Date", width=12)
        table.add_column("Progress", width=22)
        table.add_column("Duration", width=10)
        table.cursor_type = "row"
        self._populate()
        table.focus()

    def action_back(self) -> None:
        if self._scrub_mode:
            self._scrub_mode = False
            self._update_status_bar()
            self.notify("Scrub mode off", severity="information", timeout=1)
            return
        self.app.pop_screen()

    async def action_refresh(self) -> None:
        self._set_status("Full refresh ...")
        headers = self._data.get_feed_headers(self._feed_url)
        result = await fetch_feed_async(self._feed_url,
                                        etag=headers.get("etag", ""),
                                        last_modified=headers.get("last_modified", ""))
        if result.error:
            self.notify(f"Refresh failed: {result.error}", severity="error", timeout=4)
            self._set_status("Refresh failed")
            return
        if result.not_modified:
            self.notify("Feed unchanged", severity="information", timeout=2)
            self._set_status("Feed unchanged")
            return
        if result.etag or result.last_modified:
            self._data.save_feed_headers(self._feed_url, result.etag, result.last_modified)
        self._feed = result
        self._populate()
        self.notify("Feed refreshed", severity="information", timeout=2)

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        col = event.column_key
        if col == self._sort_column:
            self._sort_state = (self._sort_state + 1) % 3
        else:
            self._sort_column = col
            self._sort_state = 0
        labels = {0: "unsorted", 1: "ascending", 2: "descending"}
        logger.info("Sorted by %s %s (%d episodes)",
                    col, labels[self._sort_state], len(self._feed.episodes))
        self.notify(f"Sorted by {col} {labels[self._sort_state]}",
                    severity="information", timeout=1)
        self._populate()

    async def action_play(self) -> None:
        table = self.query_one("#episode-list", DataTable)
        cursor_row = table.cursor_row
        if cursor_row is None:
            self.notify("No episode selected", severity="warning", timeout=2)
            return
        row_key = table.ordered_rows[cursor_row].key
        episode = self._episodes_by_row.get(row_key)
        if not episode:
            self._set_status("No episode data")
            return
        await self._do_play(episode)

    @staticmethod
    def _download_episode(url: str, path: Path) -> bool:
        import urllib.request
        try:
            urllib.request.urlretrieve(url, str(path))
            return True
        except Exception as exc:
            logger.warning("Download failed for %s: %s", url, exc)
            return False

    async def _do_play(self, episode: Episode) -> None:
        if not episode.url:
            self.notify("No audio URL for this episode", severity="warning", timeout=3)
            return

        epid = episode.episode_id or ""

        if self._player.is_playing() and self._player.get_current_episode_id() == epid:
            return

        if self._player.is_playing():
            self._player.stop()

        start_pos: float | None = None
        if not self._data.is_played(epid):
            prog = self._data.get_progress(epid)
            if prog and prog.total_length > 0 and 0 < prog.position < prog.total_length - 5:
                start_pos = prog.position

        def _on_progress(eid: str, pos: float, total: float) -> None:
            self._data.save_progress(eid, pos, total)
            self._populate()

        self._player.set_current_feed_url(self._feed_url)

        audio_source = episode.url
        if start_pos is not None:
            cache_path = self._player.cache_path_for(epid)
            if cache_path.exists():
                logger.debug("Cache hit: %s", cache_path)
                audio_source = str(cache_path)
                self._player._temp_files.append(cache_path)
            else:
                self._set_status("Downloading...")
                ok = await asyncio.to_thread(self._download_episode, episode.url, cache_path)
                if ok:
                    audio_source = str(cache_path)
                    self._player._temp_files.append(cache_path)
                else:
                    self._set_status("Download failed \u2014 streaming")

        logger.debug("Playing %s (start_pos=%s, epid=%s)", audio_source, start_pos, epid)
        err = self._player.play(audio_source, epid, _on_progress, start_pos=start_pos)
        if err:
            self.notify(f"Playback failed: {err}", severity="error", timeout=5)
            return

        import time as _time
        _time.sleep(0.3)
        if start_pos is not None and not self._player.is_process_alive():
            logger.warning(
                "mpv exited quickly with start_pos=%.1f \u2014 retrying from beginning",
                start_pos,
            )
            self._player.play(audio_source, epid, _on_progress)

        self.notify(f"\u25b6  {episode.title}", severity="information", timeout=3)
        self._set_status(f"\u25b6 Playing: {episode.title}")
        live_pos, live_len = self._player.get_live_progress()
        self._player_status = PlayerStatus(
            is_playing=True, is_paused=False, position=live_pos, duration=live_len,
        )
        self._populate()
        self.post_message(PlaybackStateChanged())

    def action_add_to_queue(self) -> None:
        table = self.query_one("#episode-list", DataTable)
        cursor_row = table.cursor_row
        if cursor_row is None:
            self.notify("No episode selected", severity="warning", timeout=2)
            return
        row_key = table.ordered_rows[cursor_row].key
        episode = self._episodes_by_row.get(row_key)
        if not episode or not episode.url:
            return
        self._player.add_to_queue(episode.url, episode.episode_id or "", episode.title)
        q = self._player.queue_count
        self.notify(f"Queued: {episode.title}  [Q:{q}]", severity="information", timeout=2)
        self._update_status_bar()

    async def action_play_next(self) -> None:
        table = self.query_one("#episode-list", DataTable)
        cursor_row = table.cursor_row
        if cursor_row is None:
            return
        row_key = table.ordered_rows[cursor_row].key
        episode = self._episodes_by_row.get(row_key)
        if not episode or not episode.url:
            return
        self._player.stop()
        await self._do_play(episode)

    def action_view_queue(self) -> None:
        self.app.push_screen(QueueScreen(self._data, self._player))

    def action_stop(self) -> None:
        if self._player.is_playing():
            self._player.stop()
            self._player_status = None
            self._populate()
            self.post_message(PlaybackStateChanged())
            self.notify("Playback stopped", severity="information", timeout=2)
        else:
            self.notify("Nothing playing", severity="warning", timeout=2)

    def action_toggle_scrub(self) -> None:
        if not self._player.is_playing():
            self.notify("Nothing playing to scrub", severity="warning", timeout=2)
            return
        self._scrub_mode = not self._scrub_mode
        if self._scrub_mode:
            self.notify("Scrub mode \u2014 left/right=5s, Ctrl+left/right=1s, Escape to exit",
                        severity="information", timeout=3)
        else:
            self.notify("Scrub mode off", severity="information", timeout=1)
        self._update_status_bar()

    def action_pause(self) -> None:
        if not self._player.is_playing():
            self.notify("Nothing playing", severity="warning", timeout=2)
            return
        paused = self._player.toggle_pause()
        self._player_status = self._player.get_status()
        if paused is True:
            self.notify("\u23f8 Paused", severity="information", timeout=2)
        elif paused is False:
            self.notify("\u25b6 Resumed", severity="information", timeout=2)
        self._populate()
        self.post_message(PlaybackStateChanged())

    def action_seek_back(self) -> None:
        if not self._player.is_playing():
            self.notify("Nothing playing", severity="warning", timeout=2)
            return
        offset = 5 if self._scrub_mode else 30
        self._player.seek(-offset)
        self.notify(f"\u23ea -{offset}s", severity="information", timeout=1)

    def action_seek_forward(self) -> None:
        if not self._player.is_playing():
            self.notify("Nothing playing", severity="warning", timeout=2)
            return
        offset = 5 if self._scrub_mode else 30
        self._player.seek(offset)
        self.notify(f"\u23e9 +{offset}s", severity="information", timeout=1)

    def action_seek_fine_back(self) -> None:
        if not self._player.is_playing():
            self.notify("Nothing playing", severity="warning", timeout=2)
            return
        self._player.seek(-1)
        self.notify("\u23ea -1s", severity="information", timeout=1)

    def action_seek_fine_forward(self) -> None:
        if not self._player.is_playing():
            self.notify("Nothing playing", severity="warning", timeout=2)
            return
        self._player.seek(1)
        self.notify("\u23e9 +1s", severity="information", timeout=1)

    def action_speed_down(self) -> None:
        speeds = self._player.SPEEDS
        cur = self._player.get_speed()
        idx = speeds.index(cur) if cur in speeds else 2
        new = speeds[idx - 1] if idx > 0 else speeds[0]
        self._player.set_speed(new)
        self.notify(f"Speed: {new}x", severity="information", timeout=1)
        self._update_status_bar()

    def action_speed_up(self) -> None:
        speeds = self._player.SPEEDS
        cur = self._player.get_speed()
        idx = speeds.index(cur) if cur in speeds else 2
        new = speeds[idx + 1] if idx < len(speeds) - 1 else speeds[-1]
        self._player.set_speed(new)
        self.notify(f"Speed: {new}x", severity="information", timeout=1)
        self._update_status_bar()

    def action_toggle_filter(self) -> None:
        self._show_unplayed_only = not self._show_unplayed_only
        mode = "unplayed only" if self._show_unplayed_only else "all episodes"
        self.notify(f"Filter: {mode}", severity="information", timeout=2)
        self._populate()

    def action_toggle_played(self) -> None:
        table = self.query_one("#episode-list", DataTable)
        cursor_row = table.cursor_row
        if cursor_row is None:
            self.notify("No episode selected", severity="warning", timeout=2)
            return
        row_key = table.ordered_rows[cursor_row].key
        episode = self._episodes_by_row.get(row_key)
        if not episode:
            self._set_status("No episode data")
            return
        epid = episode.episode_id or ""
        if not epid:
            self.notify("Cannot toggle: no episode ID", severity="warning", timeout=2)
            return

        if self._data.is_played(epid):
            self._data.unmark_played(epid)
            self.notify("Marked unplayed", severity="information", timeout=2)
        else:
            self._data.mark_played(epid)
            self.notify("Marked played", severity="information", timeout=2)

        status_cell, title_cell, date_cell, bar_cell, duration_cell = self._build_row_cells(episode)
        try:
            table.update_cell(row_key, "Status", status_cell)
            table.update_cell(row_key, "Title", title_cell)
            table.update_cell(row_key, "Date", date_cell)
            table.update_cell(row_key, "Progress", bar_cell)
            table.update_cell(row_key, "Duration", duration_cell)
            table.refresh()
        except Exception as exc:
            logger.debug("Could not refresh row after toggle: %s", exc)
        self._update_status_bar()

    def action_eq_off(self) -> None:
        self._player.set_eq_preset(0)
        _, label = self._player.get_eq_preset()
        self.notify(f"EQ: {label}", severity="information", timeout=1)
        self._update_status_bar()

    def action_eq_bright(self) -> None:
        self._player.set_eq_preset(1)
        _, label = self._player.get_eq_preset()
        self.notify(f"EQ: {label}", severity="information", timeout=1)
        self._update_status_bar()

    def action_eq_warm(self) -> None:
        self._player.set_eq_preset(2)
        _, label = self._player.get_eq_preset()
        self.notify(f"EQ: {label}", severity="information", timeout=1)
        self._update_status_bar()

    def action_eq_balanced(self) -> None:
        self._player.set_eq_preset(3)
        _, label = self._player.get_eq_preset()
        self.notify(f"EQ: {label}", severity="information", timeout=1)
        self._update_status_bar()

    def action_restart(self) -> None:
        if not self._player.is_playing():
            self.notify("Nothing playing to restart", severity="warning", timeout=2)
            return
        epid = self._player.get_current_episode_id()
        if not epid:
            self.notify("No episode currently active", severity="warning", timeout=2)
            return

        episode = next((e for e in self._feed.episodes if e.episode_id == epid), None)
        if not episode:
            self.notify("Episode data not found", severity="warning", timeout=2)
            return

        self._player.stop()
        self._data.save_progress(epid, 0.0, 0.0)
        self._do_play(episode)
        self.notify("Restarting from beginning", severity="information", timeout=2)

    def action_show_details(self) -> None:
        table = self.query_one("#episode-list", DataTable)
        cursor_row = table.cursor_row
        if cursor_row is None:
            self.notify("No episode selected", severity="warning", timeout=2)
            return
        row_key = table.ordered_rows[cursor_row].key
        episode = self._episodes_by_row.get(row_key)
        if not episode:
            return
        self.app.push_screen(EpisodeDetailScreen(episode))

    def action_now_playing(self) -> None:
        if not self._player.is_playing():
            self.notify("Nothing playing", severity="warning", timeout=2)
            return
        epid = self._player.get_current_episode_id()
        if not epid:
            self.notify("No active episode", severity="warning", timeout=2)
            return
        episode = next((e for e in self._feed.episodes if e.episode_id == epid), None)
        if not episode:
            self.notify("Episode data not found", severity="warning", timeout=2)
            return
        self.app.push_screen(NowPlayingScreen(episode, self._data, self._player))

    def action_show_help(self) -> None:
        self.app.push_screen(HelpScreen(screen_name="Episode"))

    def action_quit(self) -> None:
        if self._player.is_playing():
            self._player.stop()
        self.app.exit()

    def on_click(self, event: events.Click) -> None:
        if not self._scrub_mode or not self._player.is_playing():
            return
        status = self.query_one("#ep-status", Static)
        region = status.region
        if region and region.x <= event.screen_x < region.x + region.width:
            ratio = (event.screen_x - region.x) / region.width
            dur = self._player_status.duration if self._player_status else 0
            if dur > 0:
                pos = max(0, min(ratio * dur, dur))
                self._player.seek_absolute(pos)

    def on_playback_state_changed(self, event: PlaybackStateChanged) -> None:
        self._populate()

    _refresh_counter: int = 0

    def _update_playback_progress(self) -> None:
        was_paused = self._player_status is not None and self._player_status.is_paused
        was_playing = self._player_status is not None and self._player_status.is_playing

        self._player_status = self._player.get_status()

        if self._player_status is None and self._player.is_process_alive():
            live_pos, live_len = self._player.get_live_progress()
            self._player_status = PlayerStatus(
                is_playing=True, is_paused=False, position=live_pos, duration=live_len,
            )

        now_playing = self._player_status is not None and self._player_status.is_playing
        now_paused = self._player_status is not None and self._player_status.is_paused

        if was_playing != now_playing or was_paused != now_paused:
            self._populate()
            self.post_message(PlaybackStateChanged())
            return

        self._refresh_counter += 1
        if self._refresh_counter >= 30:
            self._refresh_counter = 0
            if now_playing and self._player.get_current_episode_id():
                self._populate()
                return

        if now_playing and self._player.get_current_episode_id():
            self._refresh_playing_item()
        self._update_status_bar()

    def _refresh_playing_item(self) -> None:
        playing_eid = self._player.get_current_episode_id()
        row_key = self._row_keys.get(playing_eid) if playing_eid else None
        if row_key is None:
            playing_url = self._player.get_current_episode_url()
            if playing_url:
                for rk, ep in self._episodes_by_row.items():
                    if ep.url == playing_url:
                        row_key = rk
                        break
        if row_key is None:
            return
        ep = self._episodes_by_row.get(row_key)
        if not ep:
            return
        played = self._data.is_played(ep.episode_id or "")
        if self._player_status and self._player_status.duration > 0:
            pos = self._player_status.position
            total = self._player_status.duration
        else:
            live_pos, live_len = self._player.get_live_progress()
            pos, total = (live_pos, live_len) if live_len > 0 else (0.0, 0.0)

        title = (ep.title[:42] + "\u2026") if len(ep.title) > 42 else ep.title
        highlight = " on #003333"
        title_style = ("bold" if not played else "dim") + highlight
        title_text = Text(title, style=title_style)
        date_text = Text(format_date(ep.published), style="dim" + highlight)
        progress_text = (
            self._render_progress_bar(pos, total)
            if total > 0 else Text("\u2591" * 12, style="dim grey35" + highlight)
        )
        duration_text = Text(f"[{ep.duration or '00:00:00'}]", style="dim" + highlight)

        table = self.query_one("#episode-list", DataTable)
        try:
            table.update_cell(row_key, "Title", title_text)
            table.update_cell(row_key, "Date", date_text)
            table.update_cell(row_key, "Progress", progress_text)
            table.update_cell(row_key, "Duration", duration_text)
            table.refresh()
        except Exception:
            logger.debug("update_cell failed \u2014 row may have been removed", exc_info=True)

    MAX_VISIBLE = 100

    @staticmethod
    def _sort_episodes(
        episodes: list[Episode], column: str, sort_state: int, data: DataManager,
    ) -> list[Episode]:
        if sort_state == 0:
            return list(episodes)

        ascending = sort_state == 1

        if column == "Status":
            def key(e: Episode) -> int:
                return 0 if data.is_played(e.episode_id or "") else 1
        elif column == "Title":
            def key(e: Episode) -> str:
                return (e.title or "").lower()
        elif column == "Date":
            def key(e: Episode) -> str:
                return e.published or ""
        elif column == "Progress":
            def key(e: Episode) -> float:
                p = data.get_progress(e.episode_id or "")
                if p and not data.is_played(e.episode_id or ""):
                    return p.position
                return -1.0
        elif column == "Duration":
            def key(e: Episode) -> str:
                return e.duration or ""
        else:
            return list(episodes)

        return sorted(episodes, key=key, reverse=not ascending)

    def _populate(self) -> None:
        table = self.query_one("#episode-list", DataTable)
        if not table.ordered_columns:
            return
        self._row_keys.clear()
        self._episodes_by_row.clear()
        table.clear()

        sorted_eps = self._sort_episodes(
            self._feed.episodes, self._sort_column, self._sort_state, self._data,
        )

        episodes = sorted_eps[:self.MAX_VISIBLE]

        if self._show_unplayed_only:
            episodes = [e for e in episodes if not self._data.is_played(e.episode_id or "")]

        has_rows = False
        for ep in episodes:
            status_cell, title_cell, date_cell, bar_cell, duration_cell = self._build_row_cells(ep)
            row_key = table.add_row(status_cell, title_cell, date_cell, bar_cell, duration_cell)
            if not has_rows:
                has_rows = True
            eid = ep.episode_id or ""
            if eid:
                self._row_keys[eid] = row_key
            self._episodes_by_row[row_key] = ep

        if has_rows:
            table.move_cursor(row=0)

        direction_arrows = {0: "", 1: " \u2191", 2: " \u2193"}
        suffix = direction_arrows[self._sort_state]
        for col_key in ("Status", "Title", "Date", "Progress", "Duration"):
            col = table.columns.get(col_key)
            if col:
                col.label = col_key + (suffix if col_key == self._sort_column else "")

        self._update_status_bar()

    @staticmethod
    def _render_progress_bar(position: float, total_length: float, width: int = 0) -> Text:
        if total_length <= 0:
            return Text("")
        if width <= 0:
            width = 12
        fraction = max(min(position / total_length, 1.0), 0.0)
        filled = int(round(fraction * width))
        pct = int(fraction * 100)
        bar = Text()
        if filled:
            bar.append("\u2588" * filled, style="bold green")
        bar.append("\u2591" * (width - filled), style="dim grey35")
        bar.append(f" {pct}%", style="bold green")
        return bar

    @staticmethod
    def _render_timeline(position: float, total_length: float, width: int = 0) -> Text:
        if total_length <= 0:
            return Text("")
        if width <= 0:
            width = 20
        fraction = max(min(position / total_length, 1.0), 0.0)
        filled = int(round(fraction * width))
        bar = Text()
        bar.append("\u2588" * filled, style="bold cyan")
        bar.append("\u2591" * (width - filled), style="dim grey35")

        pos_m = int(position // 60)
        pos_s = int(position % 60)
        dur_m = int(total_length // 60)
        dur_s = int(total_length % 60)
        bar.append(f"  {pos_m}:{pos_s:02d} / {dur_m}:{dur_s:02d}", style="bold cyan")
        return bar

    def _build_row_cells(self, ep: Episode) -> tuple:
        played = self._data.is_played(ep.episode_id or "")
        prog = self._data.get_progress(ep.episode_id or "")
        has_progress = prog and prog.position > 0 and not played

        playing_eid = self._player.get_current_episode_id()
        is_playing_ep = bool(playing_eid and ep.episode_id and ep.episode_id == playing_eid)
        hl = " on #003333" if is_playing_ep else ""

        status = Text()
        status.append("[", style="dim" + hl)
        if played:
            status.append("\u2713", style="bold green" + hl)
        elif has_progress:
            status.append("\u2713", style="bold yellow" + hl)
        else:
            status.append(" ", style="dim" + hl)
        status.append("]", style="dim" + hl)

        if is_playing_ep:
            if self._player_status and self._player_status.is_playing:
                icon = "[ll]" if self._player_status.is_paused else "[\u2013>]"
                style = ("bold yellow" if self._player_status.is_paused else "bold green") + hl
                status.append(f" {icon}", style=style)
            elif self._player.is_playing():
                status.append(" [\u2013>]", style="bold green" + hl)

        title = (ep.title[:42] + "\u2026") if len(ep.title) > 42 else ep.title
        title_text = Text(title, style=("bold" if not played else "dim") + hl)

        date_text = Text(format_date(ep.published), style="dim" + hl)

        bar = Text("")
        if is_playing_ep and self._player.is_playing():
            if self._player_status and self._player_status.duration > 0:
                pos, total = self._player_status.position, self._player_status.duration
                bar = self._render_progress_bar(pos, total)
            else:
                live_pos, live_len = self._player.get_live_progress()
                if live_len > 0:
                    bar = self._render_progress_bar(live_pos, live_len)
                else:
                    bar = Text("\u2591" * 12, style="dim grey35")
        elif prog and prog.total_length > 0 and not played:
            bar = self._render_progress_bar(prog.position, prog.total_length)

        if hl and bar:
            bar.stylize(hl)

        duration_text = Text(f"[{ep.duration or '00:00:00'}]", style="dim" + hl)

        return (status, title_text, date_text, bar, duration_text)

    def _update_status_bar(self) -> None:
        total = len(self._feed.episodes)
        shown = min(total, self.MAX_VISIBLE)
        played_count = sum(
            1 for e in self._feed.episodes if self._data.is_played(e.episode_id or "")
        )
        in_progress = sum(
            1 for e in self._feed.episodes
            if (p := self._data.get_progress(e.episode_id or ""))
            and p.position > 0
            and not self._data.is_played(e.episode_id or "")
        )
        suffix = f"  (showing latest {shown} of {total})" if total > shown else ""
        filter_label = " [unplayed]" if self._show_unplayed_only else ""

        t = Text()
        stats = f" {total} ep"
        if played_count:
            stats += f"  \u2713{played_count}"
        if in_progress:
            stats += f"  \u25c7{in_progress}"
        t.append(stats, style="bold")
        t.append(" \u2502", style="dim")

        if self._player_status and self._player_status.is_playing:
            pos, dur = self._player_status.position, self._player_status.duration
            if pos <= 0 or dur <= 0:
                live_pos, live_len = self._player.get_live_progress()
                if live_pos > 0:
                    pos, dur = live_pos, live_len
            if self._scrub_mode:
                timeline = self._render_timeline(pos, dur)
                t.append(timeline)
                speed = self._player.get_speed()
                if speed != 1.0:
                    t.append(f" [{speed}x]", style="bold cyan")
                t.append(Text(" [Scrub]", style="bold yellow"))
            else:
                pos_m = int(pos // 60)
                pos_s = int(pos % 60)
                dur_m = int(dur // 60)
                dur_s = int(dur % 60)
                icon = (
                    Text(" [ll]", style="bold yellow")
                    if self._player_status.is_paused
                    else Text(" [\u2013>]", style="bold green")
                )
                t.append(icon)
                t.append(f" {pos_m}:{pos_s:02d}/{dur_m}:{dur_s:02d}", style="bold")
                speed = self._player.get_speed()
                if speed != 1.0:
                    t.append(f" [{speed}x]", style="bold cyan")
        else:
            t.append("  \u25b6 Enter to play", style="dim")

        t.append(" \u2502", style="dim")
        t.append(f" {self._feed.title}", style="bold")

        q = self._player.queue_count
        if q:
            t.append(" \u2502", style="dim")
            t.append(f" Q:{q}", style="bold cyan")

        _, eq_label = self._player.get_eq_preset()
        if eq_label != "Off":
            t.append(" \u2502", style="dim")
            t.append(f" EQ:{eq_label}", style="bold yellow")

        t.append(" \u2502", style="dim")
        t.append(f" ? help{filter_label}", style="dim")
        t.append(suffix, style="dim")

        self._set_status(t)

    def _set_status(self, msg: str | Text) -> None:
        try:
            spinner = self.query_one("#ep-status", LoadingSpinner)
            spinner.stop()
            spinner.update(msg)
        except Exception as exc:
            logger.debug("Episode status widget not ready: %s", exc)
