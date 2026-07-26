# Created: 2026-07-19
# Last Edited: 2026-07-25 17:45 CT (America/Chicago)
# Path: src/screens.py
# Purpose: Textual screens for AetherPod — feed list, episode list, and add-feed dialog.

from __future__ import annotations

import asyncio
import datetime
import logging
import re
from email import utils as email_utils

from textual.app import ComposeResult
from textual.binding import Binding
from textual import events
from textual.message import Message
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

from rich.text import Text

from src.engine import DataManager, Episode, FeedResult, ProgressInfo, fetch_feed_async
from src.player import Player
from src.engines import PlayerStatus
from src.widgets import LoadingSpinner

logger = logging.getLogger(__name__)


class PlaybackStateChanged(Message):
    """Posted when playback state (playing/paused/stopped) changes.

    Handled by EpisodeScreen to force a UI refresh.
    """


class FeedScreen(Screen):
    """Feed subscription list — the main entry screen.

    Shows subscribed feeds in a ListView with episode counts. Loads from
    cache instantly, then background-refreshes. Press ``Enter`` to browse
    a feed's episodes, ``/`` to search across all feeds.

    Actions:
        a      — add a feed URL
        i      — import feeds from OPML
        e      — export feeds to OPML
        u      — refresh all feeds
        /      — search across all feeds
        r      — remove the selected feed
        Enter  — browse episodes for this feed
        q      — quit AetherPod
        ?      — show help
    """

    BINDINGS = [
        Binding("a", "add_feed", "Add Feed"),
        Binding("i", "import_opml", "Import OPML"),
        Binding("e", "export_opml", "Export OPML"),
        Binding("u", "refresh", "Refresh"),
        Binding("r", "remove_feed", "Remove"),
        Binding("slash", "search", "Search", key_display="/"),
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "show_help", "Help", key_display="?"),
    ]

    def __init__(self, data_manager: DataManager, player: Player) -> None:
        super().__init__()
        self._data = data_manager
        self._player = player

    def compose(self) -> ComposeResult:
        yield Header()
        yield LoadingSpinner(id="feed-status")
        yield ListView(id="feed-list")
        yield Footer()

    async def on_mount(self) -> None:
        # Load from cache immediately, then background refresh
        self._render_from_cache()
        # Fire background refresh without blocking
        asyncio.create_task(self._refresh_feeds())

    # ── actions ─────────────────────────────────────────────────────

    def action_add_feed(self) -> None:
        """Open input dialog, add the returned URL, then refresh."""

        def _on_url(url: str | None) -> None:
            if url:
                if self._data.add_feed(url):
                    self.notify("Feed added", severity="information", timeout=3)
                else:
                    self.notify("Feed already subscribed", severity="warning", timeout=3)
                asyncio.create_task(self._refresh_feeds())

        self.app.push_screen(AddFeedDialog(), _on_url)

    async def action_refresh(self) -> None:
        """Re-fetch all feeds and update the list."""
        await self._refresh_feeds()

    def action_remove_feed(self) -> None:
        """Remove the currently highlighted feed."""
        feed_list = self.query_one("#feed-list", ListView)
        if feed_list.index is None:
            self.notify("No feed selected", severity="warning", timeout=2)
            return
        item = feed_list.children[feed_list.index]
        url: str | None = getattr(item, "_feed_url", None)
        if url:
            self._data.remove_feed(url)
            self.notify("Removed feed", severity="information", timeout=2)
            asyncio.create_task(self._refresh_feeds())

    def action_quit(self) -> None:
        """Stop playback (if any) then exit the application."""
        if self._player.is_playing():
            self._player.stop()
        self.app.exit()

    def action_import_opml(self) -> None:
        """Open path dialog, import OPML, then refresh."""

        def _on_path(path: str | None) -> None:
            if path:
                count = self._data.opml_import(path)
                if count > 0:
                    self.notify(f"Imported {count} feed(s)", severity="information", timeout=3)
                else:
                    self.notify("No new feeds found", severity="warning", timeout=3)
                asyncio.create_task(self._refresh_feeds())

        self.app.push_screen(PathInputDialog("Import OPML", "path/to/subscriptions.opml"), _on_path)

    def action_export_opml(self) -> None:
        """Open path dialog, export feeds to OPML."""

        def _on_path(path: str | None) -> None:
            if path:
                count = self._data.opml_export(path)
                if count > 0:
                    self.notify(f"Exported {count} feed(s)", severity="information", timeout=3)
                else:
                    self.notify("No feeds to export", severity="warning", timeout=3)

        self.app.push_screen(PathInputDialog("Export OPML", "aetherpod_subscriptions.opml"), _on_path)

    def action_search(self) -> None:
        """Search across all feeds."""
        self.app.push_screen(SearchScreen(self._data, self._player))

    def action_show_help(self) -> None:
        """Show the in-app help overlay."""
        self.app.push_screen(HelpScreen(screen_name="Feed"))

    # ── internal ────────────────────────────────────────────────────

    _last_playing_feed: str = ""

    def _update_playing_indicator(self, playing_feed_url: str) -> None:
        """Re-render feed list if the playing feed changed (▶ indicator)."""
        if playing_feed_url != self._last_playing_feed:
            self._last_playing_feed = playing_feed_url
            self._render_from_cache()

    def _render_from_cache(self) -> None:
        """Render the feed list from cached results (instant startup)."""
        urls = self._data.get_feeds()
        feed_list = self.query_one("#feed-list", ListView)
        try:
            feed_list.clear()
        except ValueError:
            logger.debug("Ignored ListView hover race during clear")

        if not urls:
            feed_list.append(ListItem(Label("No feeds — press 'a' to add one")))
            self._set_status("No feeds subscribed")
            return

        has_cache = False
        playing_feed_url = self._player.get_current_feed_url() if self._player.is_playing() else ""

        for url in urls:
            cached = self._data.get_cached_result(url)
            item = ListItem()
            item._feed_url = url  # type: ignore[attr-defined]
            item._feed_result = cached  # type: ignore[attr-defined]
            if cached is not None:
                has_cache = True
                total = len(cached.episodes)
                played = sum(
                    1 for e in cached.episodes if self._data.is_played(e.episode_id or "")
                )
                unplayed = total - played
                prefix = "▶ " if url == playing_feed_url else ""
                label = Label(f"{prefix}{cached.title}  ({total} ep, {unplayed} new)")
            else:
                label = Label(f"  {url}  (waiting...)")
            item.compose_add_child(label)
            feed_list.append(item)

        if urls:
            if has_cache:
                self._start_spinner(f"{len(urls)} feed{'s' if len(urls) != 1 else ''} — refreshing...")
            else:
                self._start_spinner(f"{len(urls)} feed{'s' if len(urls) != 1 else ''} — loading...")

    async def _refresh_feeds(self) -> None:
        """Fetch all feeds in parallel and update the list."""
        urls = self._data.get_feeds()
        feed_list = self.query_one("#feed-list", ListView)

        if not urls:
            return

        self._start_spinner(f"Refreshing {len(urls)} feed(s)...")

        # Fetch all feeds in parallel using aiohttp (auto-refresh: last N days)
        tasks = []
        for url in urls:
            headers = self._data.get_feed_headers(url)
            tasks.append(
                fetch_feed_async(url,
                                 etag=headers.get("etag", ""),
                                 last_modified=headers.get("last_modified", ""),
                                  days_back=self._data.get_refresh_days())
            )
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Rebuild the list from fetched results
        try:
            feed_list.clear()
        except ValueError:
            logger.debug("Ignored ListView hover race during refresh")
        for url, result in zip(urls, results):
            item = ListItem()
            item._feed_url = url  # type: ignore[attr-defined]

            playing_feed_url = self._player.get_current_feed_url() if self._player.is_playing() else ""
            prefix = "▶ " if url == playing_feed_url else ""

            if isinstance(result, Exception):
                logger.warning("Feed fetch exception for %s: %s", url, result)
                item._feed_result = None  # type: ignore[attr-defined]
                label = Label(f"{prefix}✗ {url} — {result}")
            elif result.not_modified:
                cached = self._data.get_cached_result(url)
                item._feed_result = cached  # type: ignore[attr-defined]
                if cached:
                    total = len(cached.episodes)
                    played = sum(1 for e in cached.episodes if self._data.is_played(e.episode_id or ""))
                    unplayed = total - played
                    label = Label(f"{prefix}{cached.title}  ({total} ep, {unplayed} new)")
                else:
                    label = Label(f"{prefix}  {url}  (unchanged)")
            elif result.error:
                cached = self._data.get_cached_result(url)
                item._feed_result = cached  # type: ignore[attr-defined]
                if cached:
                    total = len(cached.episodes)
                    played = sum(1 for e in cached.episodes if self._data.is_played(e.episode_id or ""))
                    unplayed = total - played
                    label = Label(f"{prefix}⚠ {cached.title}  ({total} ep, {unplayed} new)  — {result.error}")
                else:
                    label = Label(f"{prefix}✗ {url} — {result.error}")
            else:
                if result.etag or result.last_modified:
                    self._data.save_feed_headers(url, result.etag, result.last_modified)
                self._data.save_cached_result(url, result)
                item._feed_result = result  # type: ignore[attr-defined]
                total = len(result.episodes)
                played = sum(
                    1 for e in result.episodes if self._data.is_played(e.episode_id or "")
                )
                unplayed = total - played
                label = Label(f"{prefix}{result.title}  ({total} ep, {unplayed} new)")

            item.compose_add_child(label)
            feed_list.append(item)

        n = len(urls)
        self._set_status(f"{n} feed{'s' if n != 1 else ''} — 'a' to add, Enter to browse")

    def _start_spinner(self, msg: str) -> None:
        try:
            self.query_one("#feed-status", LoadingSpinner).start(msg)
        except Exception:
            pass

    def _set_status(self, msg: str) -> None:
        try:
            spinner = self.query_one("#feed-status", LoadingSpinner)
            spinner.stop()
            spinner.update(msg)
        except Exception:
            pass

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle Enter on a feed item — push the episode browser."""
        item = event.item
        result: FeedResult | None = getattr(item, "_feed_result", None)
        url: str | None = getattr(item, "_feed_url", None)
        if result is not None and result.error:
            self._set_status(f"✗ {result.error}")
            self.notify(f"Cannot browse: {result.error}", severity="error", timeout=4)
        elif result is not None and result.episodes:
            self.app.push_screen(EpisodeScreen(result, url, self._data, self._player))
        elif result is not None:
            self._set_status(f"No episodes in '{result.title}'")
        else:
            self._set_status("No data for this feed")


class EpisodeScreen(Screen):
    """Episode browser for a single feed — play, filter, sort, scrub.

    Shows episodes in a DataTable with status icons, progress bars, and
    sortable columns. Live progress updates every 1s via AetherPod's poll.

    Actions:
        escape  — go back / exit scrub mode
        Enter   — play the selected episode
        space   — toggle pause/resume
        s       — stop playback
        m       — toggle played/unplayed
        r       — restart from beginning
        d       — show episode details
        N       — now-playing full-screen view
        u       — full refresh (no date limit)
        f       — toggle unplayed-only filter
        ← / →   — seek -30s / +30s (5s in scrub mode)
        [ / ]   — speed down / up
        .       — toggle scrub mode
        q       — quit AetherPod
        ?       — show help
    """

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
        # Starting Title column width (auto-fill column that users want to adjust)
        self._title_width: int = 42
        # Sort state: 0=unsorted (natural), 1=ascending, 2=descending
        self._sort_column: str = "Date"
        self._sort_state: int = 0  # unsorted — natural feed order
        # Maps episode_id → DataTable row_key for progress updates
        self._row_keys: dict[str, str] = {}
        # Maps row_key → Episode for cursor-based selection
        self._episodes_by_row: dict[str, Episode] = {}
        # ── scrub mode ─────────────────────────────────────────────────
        self._scrub_mode: bool = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield LoadingSpinner(id="ep-status")
        yield DataTable(id="episode-list")
        yield Footer()

    async def on_mount(self) -> None:
        # If something is already playing, grab live status immediately
        if self._player.is_process_alive():
            status = self._player.get_status()
            if status is None:
                live_pos, live_len = self._player.get_live_progress()
                if live_pos > 0:
                    status = PlayerStatus(is_playing=True, is_paused=False,
                                          position=live_pos, duration=live_len)
            self._player_status = status

        table = self.query_one("#episode-list", DataTable)
        # Add columns individually so we can set initial widths
        table.add_column("Status", width=8)
        table.add_column("Title", width=self._title_width)
        table.add_column("Date", width=12)
        table.add_column("Progress", width=22)
        table.add_column("Duration", width=10)
        table.cursor_type = "row"
        self._populate()
        # Focus the DataTable so keyboard navigation works immediately
        table.focus()
        # Player status polling is handled by a 1s interval in AetherPod
        # (src/app.py _poll_playback) which calls _update_playback_progress()

    # ── actions ─────────────────────────────────────────────────────

    def action_back(self) -> None:
        """Go back to the feed list, or exit scrub mode first."""
        if self._scrub_mode:
            self._scrub_mode = False
            self._update_status_bar()
            self.notify("Scrub mode off", severity="information", timeout=1)
            return
        self.app.pop_screen()

    async def action_refresh(self) -> None:
        """Re-fetch the feed and update episode list (full refresh — no date limit)."""
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
        """Handle click on a column header — 3-state cycle: unsorted → ascending → descending."""
        col = event.column_key
        if col == self._sort_column:
            # Same column: advance to next state (0→1→2→0)
            self._sort_state = (self._sort_state + 1) % 3
        else:
            # Different column: start at unsorted
            self._sort_column = col
            self._sort_state = 0
        labels = {0: "unsorted", 1: "ascending", 2: "descending"}
        logger.info("Sorted by %s %s (%d episodes)", col, labels[self._sort_state], len(self._feed.episodes))
        self.notify(f"Sorted by {col} {labels[self._sort_state]}",
                    severity="information", timeout=1)
        self._populate()

    async def action_play(self) -> None:
        """Play the selected episode via mpv."""
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
        """Download a podcast episode to a local cache file. Runs in executor."""
        import urllib.request
        try:
            urllib.request.urlretrieve(url, str(path))
            return True
        except Exception as exc:
            logger.warning("Download failed for %s: %s", url, exc)
            return False

    async def _do_play(self, episode: Episode) -> None:
        """Start playback for *episode* via mpv — downloads first when resuming."""
        if not episode.url:
            self.notify("No audio URL for this episode", severity="warning", timeout=3)
            return

        epid = episode.episode_id or ""

        # If already playing this exact episode, ignore double-Enter
        if self._player.is_playing() and self._player.get_current_episode_id() == epid:
            return

        # If already playing something else, stop it first
        if self._player.is_playing():
            self._player.stop()

        # Resume from saved progress (skip if fully played)
        start_pos: float | None = None
        if not self._data.is_played(epid):
            prog = self._data.get_progress(epid)
            if prog and prog.total_length > 0 and 0 < prog.position < prog.total_length - 5:
                start_pos = prog.position

        def _on_progress(eid: str, pos: float, total: float) -> None:
            self._data.save_progress(eid, pos, total)
            self._populate()

        self._player.set_current_feed_url(self._feed_url)

        # Determine audio source: cache local file for resume, else stream URL
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
                    self._set_status("Download failed — streaming")

        logger.debug("Playing %s (start_pos=%s, epid=%s)", audio_source, start_pos, epid)
        err = self._player.play(audio_source, epid, _on_progress, start_pos=start_pos)
        if err:
            self.notify(f"Playback failed: {err}", severity="error", timeout=5)
            return

        # If mpv exits immediately (CDN rejects --start), retry from beginning
        import time as _time
        _time.sleep(0.3)
        if start_pos is not None and not self._player.is_process_alive():
            logger.warning("mpv exited quickly with start_pos=%.1f — retrying from beginning", start_pos)
            self._player.play(audio_source, epid, _on_progress)

        self.notify(f"▶  {episode.title}", severity="information", timeout=3)
        self._set_status(f"▶ Playing: {episode.title}")
        live_pos, live_len = self._player.get_live_progress()
        self._player_status = PlayerStatus(
            is_playing=True,
            is_paused=False,
            position=live_pos,
            duration=live_len,
        )
        self._populate()
        self.post_message(PlaybackStateChanged())

    def action_add_to_queue(self) -> None:
        """Add the selected episode to the play queue."""
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
        """Stop current and play selected immediately (plays next)."""
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
        """Open the queue screen."""
        self.app.push_screen(QueueScreen(self._data, self._player))

    def action_stop(self) -> None:
        """Stop current playback."""
        if self._player.is_playing():
            self._player.stop()
            self._player_status = None
            self._populate()
            self.post_message(PlaybackStateChanged())
            self.notify("Playback stopped", severity="information", timeout=2)
        else:
            self.notify("Nothing playing", severity="warning", timeout=2)

    def action_toggle_scrub(self) -> None:
        """Toggle scrub mode — fine-seeking with timeline bar in status bar."""
        if not self._player.is_playing():
            self.notify("Nothing playing to scrub", severity="warning", timeout=2)
            return
        self._scrub_mode = not self._scrub_mode
        if self._scrub_mode:
            self.notify("🔍 Scrub mode — left/right=5s, Ctrl+left/right=1s, Escape to exit",
                        severity="information", timeout=3)
        else:
            self.notify("Scrub mode off", severity="information", timeout=1)
        self._update_status_bar()

    def action_pause(self) -> None:
        """Toggle pause/resume via IPC."""
        if not self._player.is_playing():
            self.notify("Nothing playing", severity="warning", timeout=2)
            return
        paused = self._player.toggle_pause()
        # Refresh status immediately so the UI indicator flips right away
        self._player_status = self._player.get_status()
        if paused is True:
            self.notify("⏸ Paused", severity="information", timeout=2)
        elif paused is False:
            self.notify("▶ Resumed", severity="information", timeout=2)
        self._populate()
        self.post_message(PlaybackStateChanged())

    def action_seek_back(self) -> None:
        """Seek backward — 30s normally, 5s in scrub mode."""
        if not self._player.is_playing():
            self.notify("Nothing playing", severity="warning", timeout=2)
            return
        offset = 5 if self._scrub_mode else 30
        self._player.seek(-offset)
        self.notify(f"⏪ -{offset}s", severity="information", timeout=1)

    def action_seek_forward(self) -> None:
        """Seek forward — 30s normally, 5s in scrub mode."""
        if not self._player.is_playing():
            self.notify("Nothing playing", severity="warning", timeout=2)
            return
        offset = 5 if self._scrub_mode else 30
        self._player.seek(offset)
        self.notify(f"⏩ +{offset}s", severity="information", timeout=1)

    def action_seek_fine_back(self) -> None:
        """Seek backward 1 second (scrub mode fine control)."""
        if not self._player.is_playing():
            self.notify("Nothing playing", severity="warning", timeout=2)
            return
        self._player.seek(-1)
        self.notify("⏪ -1s", severity="information", timeout=1)

    def action_seek_fine_forward(self) -> None:
        """Seek forward 1 second (scrub mode fine control)."""
        if not self._player.is_playing():
            self.notify("Nothing playing", severity="warning", timeout=2)
            return
        self._player.seek(1)
        self.notify("⏩ +1s", severity="information", timeout=1)

    def action_speed_down(self) -> None:
        """Decrease playback speed."""
        speeds = self._player.SPEEDS
        cur = self._player.get_speed()
        idx = speeds.index(cur) if cur in speeds else 2
        new = speeds[idx - 1] if idx > 0 else speeds[0]
        self._player.set_speed(new)
        self.notify(f"Speed: {new}x", severity="information", timeout=1)
        self._update_status_bar()

    def action_speed_up(self) -> None:
        """Increase playback speed."""
        speeds = self._player.SPEEDS
        cur = self._player.get_speed()
        idx = speeds.index(cur) if cur in speeds else 2
        new = speeds[idx + 1] if idx < len(speeds) - 1 else speeds[-1]
        self._player.set_speed(new)
        self.notify(f"Speed: {new}x", severity="information", timeout=1)
        self._update_status_bar()

    def action_toggle_filter(self) -> None:
        """Toggle between showing all episodes and unplayed-only."""
        self._show_unplayed_only = not self._show_unplayed_only
        mode = "unplayed only" if self._show_unplayed_only else "all episodes"
        self.notify(f"Filter: {mode}", severity="information", timeout=2)
        self._populate()

    def action_toggle_played(self) -> None:
        """Toggle the selected episode's played/unplayed status.

        Key: ``m`` (mnemonic: "mark").

        If the episode is currently marked played, it is unmarked and
        any saved progress is cleared.  If unplayed, it is marked played.
        Updates the row in-place via ``update_cell`` so the list doesn't
        re-sort (unless the user clicks a header).
        """
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

        # Refresh just the affected row cells
        status_cell, title_cell, date_cell, bar_cell, duration_cell = self._build_row_cells(episode)
        try:
            table.update_cell(row_key, "Status", status_cell)
            table.update_cell(row_key, "Title", title_cell)
            table.update_cell(row_key, "Date", date_cell)
            table.update_cell(row_key, "Progress", bar_cell)
            table.update_cell(row_key, "Duration", duration_cell)
            table.refresh()
        except Exception:
            pass
        self._update_status_bar()

    def action_restart(self) -> None:
        """Restart the currently-playing episode from the beginning.

        Key: ``r`` (mnemonic: "restart").

        Stops mpv, clears saved progress for the current episode, and
        re-plays from position 0.
        """
        if not self._player.is_playing():
            self.notify("Nothing playing to restart", severity="warning", timeout=2)
            return
        epid = self._player.get_current_episode_id()
        if not epid:
            self.notify("No episode currently active", severity="warning", timeout=2)
            return

        # Find the episode in the feed's episode list
        episode = next((e for e in self._feed.episodes if e.episode_id == epid), None)
        if not episode:
            self.notify("Episode data not found", severity="warning", timeout=2)
            return

        # Stop and clear progress
        self._player.stop()
        self._data.save_progress(epid, 0.0, 0.0)

        # Re-play from beginning
        self._do_play(episode)
        self.notify("Restarting from beginning", severity="information", timeout=2)

    def action_show_details(self) -> None:
        """Show episode details (description, link) in a modal."""
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
        """Open the now-playing screen for the current playback."""
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
        """Show the in-app help overlay."""
        self.app.push_screen(HelpScreen(screen_name="Episode"))

    def action_column_wider(self) -> None:
        """Increase the Title column width."""
        self._title_width = min(80, self._title_width + 4)
        self._resize_title_column()

    def _resize_title_column(self) -> None:
        """Update the Title column width and refresh the table."""
        table = self.query_one("#episode-list", DataTable)
        for col_key, col in table.columns.items():
            label = col.label.plain if col.label else ""
            if label == "Title":
                col.width = self._title_width
                col.auto_width = False
                break
        self._populate()
        self.notify(f"Title width: {self._title_width}", severity="information", timeout=1)

    def action_quit(self) -> None:
        """Stop playback (if any) then exit the application."""
        if self._player.is_playing():
            self._player.stop()
        self.app.exit()

    def on_click(self, event: events.Click) -> None:
        """Handle mouse clicks — during scrub mode, click on the timeline bar to seek."""
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
        """Handle PlaybackStateChanged — refresh the episode row in view."""
        self._populate()

    _refresh_counter: int = 0

    def _update_playback_progress(self) -> None:
        """Called every 1s from AetherPod — update progress bar + status bar.

        Checks for play/pause state transitions; on state change triggers a
        full list repopulate.  Otherwise only refreshes the currently-playing
        episode's progress bar and the status bar position/duration text.

        Falls back to :meth:`Player.is_playing` + :meth:`Player.get_live_progress`
        when the IPC socket is not yet connected (startup transient).
        """
        was_paused = self._player_status is not None and self._player_status.is_paused
        was_playing = self._player_status is not None and self._player_status.is_playing

        # Query IPC status (may return None if socket not ready or transient error)
        self._player_status = self._player.get_status()

        # Fallback: if IPC returned None but the mpv process is alive, synthesise
        # a PlayerStatus from stdout live progress data (available immediately).
        # Uses is_process_alive() (no side effects) instead of is_playing()
        # to avoid the TOCTOU race where the process dies between two calls.
        if self._player_status is None and self._player.is_process_alive():
            live_pos, live_len = self._player.get_live_progress()
            self._player_status = PlayerStatus(
                is_playing=True,
                is_paused=False,
                position=live_pos,
                duration=live_len,
            )

        now_playing = self._player_status is not None and self._player_status.is_playing
        now_paused = self._player_status is not None and self._player_status.is_paused

        # Full repopulate on state transition
        if was_playing != now_playing or was_paused != now_paused:
            self._populate()
            self.post_message(PlaybackStateChanged())
            return

        # Full repopulate every 30s to force DataTable progress bar refresh
        self._refresh_counter += 1
        if self._refresh_counter >= 30:
            self._refresh_counter = 0
            if now_playing and self._player.get_current_episode_id():
                self._populate()
                return

        # When actively playing, refresh progress bar + status text every tick
        if now_playing and self._player.get_current_episode_id():
            self._refresh_playing_item()
        self._update_status_bar()

    def _refresh_playing_item(self) -> None:
        """Update the DataTable row for the currently-playing episode with fresh progress."""
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

        title = (ep.title[:42] + "…") if len(ep.title) > 42 else ep.title
        highlight = "on #003333"
        title_style = ("bold" if not played else "dim") + highlight
        title_text = Text(title, style=title_style)
        date_text = Text(self._format_date(ep.published), style="dim" + highlight)
        progress_text = self._render_progress_bar(pos, total) if total > 0 else Text("░" * 12, style="dim grey35" + highlight)
        duration_text = Text(f"[{ep.duration or '00:00:00'}]", style="dim" + highlight)

        table = self.query_one("#episode-list", DataTable)
        try:
            table.update_cell(row_key, "Title", title_text)
            table.update_cell(row_key, "Date", date_text)
            table.update_cell(row_key, "Progress", progress_text)
            table.update_cell(row_key, "Duration", duration_text)
            table.refresh()
        except Exception:
            logger.debug("update_cell failed — row may have been removed", exc_info=True)

    # ── internal ────────────────────────────────────────────────────

    MAX_VISIBLE = 100

    # ── Sort helpers ─────────────────────────────────────────────

    @staticmethod
    def _sort_episodes(
        episodes: list[Episode],
        column: str,
        sort_state: int,
        data: DataManager,
    ) -> list[Episode]:
        """Return a new sorted list of episodes by *column*.

        *sort_state*: 0=unsorted (natural order), 1=ascending, 2=descending.
        Column must be one of Status, Title, Date, Progress, Duration.
        Returns the list unchanged when *sort_state* is 0.
        """
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
        """Populate (or re-populate) the episode DataTable with current sort + filter."""
        self._row_keys.clear()
        self._episodes_by_row.clear()
        table = self.query_one("#episode-list", DataTable)
        table.clear()

        # Sort episodes by the current column / direction
        sorted_eps = self._sort_episodes(
            self._feed.episodes,
            self._sort_column,
            self._sort_state,
            self._data,
        )

        # Cap to MAX_VISIBLE after sorting
        episodes = sorted_eps[: self.MAX_VISIBLE]

        # Apply unplayed-only filter when toggled
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

        # Move cursor to the first row so Enter works immediately
        if has_rows:
            table.move_cursor(row=0)

        # Annotate the sorted column's header with direction indicator
        direction_arrows = {0: "", 1: " ↑", 2: " ↓"}
        suffix = direction_arrows[self._sort_state]
        for col_key in ("Status", "Title", "Date", "Progress", "Duration"):
            col = table.columns.get(col_key)
            if col:
                col.label = col_key + (suffix if col_key == self._sort_column else "")

        self._update_status_bar()

    @staticmethod
    def _format_date(raw: str | None) -> str:
        """Parse a feed date string and return ``YYYY-MM-DD``, or ``"?"`` on failure.

        Handles both ISO 8601 (Atom) and RFC 2822 (RSS) date formats.
        """
        if not raw:
            return "?"
        raw = raw.strip()
        # Try ISO 8601 first (Atom feeds)
        try:
            dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass
        # Try RFC 2822 (RSS feeds)
        try:
            dt = email_utils.parsedate_to_datetime(raw)
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError, LookupError):
            pass
        # Last resort — return the first 10 chars as a passthrough
        return raw[:10]

    @staticmethod
    def _render_progress_bar(
        position: float, total_length: float, width: int = 0
    ) -> Text:
        """Render a progress bar as a Rich ``Text`` with block characters.

        Filled portion uses bold green ``█``, unfilled uses dim dark-gray ``░``.
        *width* defaults to 0 (auto — uses proportional width).
        Returns an empty ``Text`` when there is nothing to display.
        """
        if total_length <= 0:
            return Text("")
        if width <= 0:
            width = 12
        fraction = max(min(position / total_length, 1.0), 0.0)
        filled = int(round(fraction * width))
        pct = int(fraction * 100)
        bar = Text()
        if filled:
            bar.append("█" * filled, style="bold green")
        bar.append("░" * (width - filled), style="dim grey35")
        bar.append(f" {pct}%", style="bold green")
        return bar

    @staticmethod
    def _render_timeline(
        position: float, total_length: float, width: int = 0
    ) -> Text:
        """Render a timeline bar for scrub mode — block chars + ``MM:SS / MM:SS``.

        *width* defaults to 0 (auto — uses proportional width).
        Returns a Rich ``Text`` suitable for the status bar during scrub mode.
        Returns an empty ``Text`` when total_length is zero.
        """
        if total_length <= 0:
            return Text("")
        if width <= 0:
            width = 20
        fraction = max(min(position / total_length, 1.0), 0.0)
        filled = int(round(fraction * width))
        bar = Text()
        bar.append("█" * filled, style="bold cyan")
        bar.append("░" * (width - filled), style="dim grey35")

        pos_m = int(position // 60)
        pos_s = int(position % 60)
        dur_m = int(total_length // 60)
        dur_s = int(total_length % 60)
        bar.append(f"  {pos_m}:{pos_s:02d} / {dur_m}:{dur_s:02d}", style="bold cyan")
        return bar

    def _build_row_cells(self, ep: Episode) -> tuple:
        """Build a 5-tuple of renderables for one DataTable row.

        Columns: Status, Title, Date, Progress, Duration

        Status shows ``[✓]`` for fully-played (green) or partially-played
        (yellow) episodes; shows ``[ ]`` for completely unplayed episodes.
        """
        played = self._data.is_played(ep.episode_id or "")
        prog = self._data.get_progress(ep.episode_id or "")
        has_progress = prog and prog.position > 0 and not played

        # Determine if this is the currently-playing episode
        playing_eid = self._player.get_current_episode_id()
        is_playing_ep = bool(playing_eid and ep.episode_id and ep.episode_id == playing_eid)
        hl = " on #003333" if is_playing_ep else ""

        # Status bracket: [✓] or [ ]
        status = Text()
        status.append("[", style="dim" + hl)
        if played:
            status.append("✓", style="bold green" + hl)
        elif has_progress:
            status.append("✓", style="bold yellow" + hl)
        else:
            status.append(" ", style="dim" + hl)
        status.append("]", style="dim" + hl)

        # Status indicator for currently-playing / paused episode
        if is_playing_ep:
            if self._player_status and self._player_status.is_playing:
                icon = "[ll]" if self._player_status.is_paused else "[->]"
                style = ("bold yellow" if self._player_status.is_paused else "bold green") + hl
                status.append(f" {icon}", style=style)
            elif self._player.is_playing():
                status.append(" [->]", style="bold green" + hl)

        # Episode title (truncated for single-line compactness)
        title = (ep.title[:42] + "…") if len(ep.title) > 42 else ep.title
        title_text = Text(title, style=("bold" if not played else "dim") + hl)

        # Publish date — always YYYY-MM-DD
        date_text = Text(self._format_date(ep.published), style="dim" + hl)

        # Progress bar — prefer IPC status, fall back to stdout live progress
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
                    bar = Text("░" * 12, style="dim grey35")
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
            if (p := self._data.get_progress(e.episode_id or "")) and p.position > 0 and not self._data.is_played(e.episode_id or "")
        )
        suffix = f"  (showing latest {shown} of {total})" if total > shown else ""
        filter_label = " [unplayed]" if self._show_unplayed_only else ""

        t = Text()
        # Left segment: episode stats
        stats = f" {total} ep"
        if played_count:
            stats += f"  ✓{played_count}"
        if in_progress:
            stats += f"  ◎{in_progress}"
        t.append(stats, style="bold")
        t.append(" │", style="dim")

        # Center segment: playback status
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
                icon = Text(" [ll]", style="bold yellow") if self._player_status.is_paused else Text(" [->]", style="bold green")
                t.append(icon)
                t.append(f" {pos_m}:{pos_s:02d}/{dur_m}:{dur_s:02d}", style="bold")
                speed = self._player.get_speed()
                if speed != 1.0:
                    t.append(f" [{speed}x]", style="bold cyan")
        else:
            t.append("  ▶ Enter to play", style="dim")

        # Feed name
        t.append(" │", style="dim")
        t.append(f" {self._feed.title}", style="bold")

        # Queue count
        q = self._player.queue_count
        if q:
            t.append(" │", style="dim")
            t.append(f" Q:{q}", style="bold cyan")

        # Right segment: hints
        t.append(" │", style="dim")
        t.append(f" ? help{filter_label}", style="dim")
        t.append(suffix, style="dim")

        self._set_status(t)

    def _set_status(self, msg: str | Text) -> None:
        try:
            spinner = self.query_one("#ep-status", LoadingSpinner)
            spinner.stop()
            spinner.update(msg)
        except Exception:
            pass


class AddFeedDialog(Screen[str | None]):
    """Modal dialog for entering a feed URL.

    Calls self.dismiss(url) on submit, or self.dismiss(None) on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("", id="dialog-box")
        yield Static("Add Feed URL", classes="dialog-title")
        yield Input(placeholder="https://example.com/feed.xml", id="feed-url-input")
        yield Static("", id="feed-url-error", classes="dialog-error")
        yield Button("Add", id="add-feed-btn", variant="primary")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self._submit()

    def _validate_url(self, url: str) -> str | None:
        import re
        if not url:
            return "Please enter a URL"
        if not re.match(r'^https?://', url):
            return "URL must start with http:// or https://"
        if '.' not in url:
            return "URL seems invalid (no domain)"
        return None

    def _submit(self) -> None:
        url = self.query_one(Input).value.strip()
        error = self._validate_url(url)
        if error:
            t = Text(error, style="bold #ff6b6b")
            self.query_one("#feed-url-error", Static).update(t)
            self.notify(error, severity="warning", timeout=3)
        else:
            self.dismiss(url)


class PathInputDialog(Screen[str | None]):
    """Modal dialog for entering a file path (import/export).

    Calls self.dismiss(path) on submit, or self.dismiss(None) on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, title: str, placeholder: str = "path/to/file") -> None:
        super().__init__()
        self._title = title
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        yield Static(self._title, classes="dialog-title")
        yield Input(placeholder=self._placeholder, id="path-input")
        yield Static("", id="path-error", classes="dialog-error")
        yield Button("Submit", id="path-submit-btn", variant="primary")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self._submit()

    def _submit(self) -> None:
        path = self.query_one(Input).value.strip()
        if path:
            self.dismiss(path)
        else:
            error = Text("Please enter a path", style="bold #ff6b6b")
            self.query_one("#path-error", Static).update(error)
            self.notify("Please enter a path", severity="warning", timeout=3)


class NowPlayingScreen(Screen[None]):
    """Full-screen now-playing view with big progress bar, metadata, and controls.

    Shows the current episode's title, a 50-character progress bar with
    percentage, time elapsed / total, playback speed, and description.
    Refreshes every 0.5s via its own interval timer (also triggered by
    AetherPod's 1s poll when it's the top screen).

    Actions:
        Esc / N  — close
        Space    — pause / resume
        s        — stop and return
        ← / →    — seek -30s / +30s
        [ / ]    — speed down / up
    """

    BINDINGS = [
        Binding("escape,n", "dismiss", "Close"),
        Binding("space", "pause", "Pause"),
        Binding("s", "stop", "Stop"),
        Binding("left", "seek_back", "-30s"),
        Binding("right", "seek_forward", "+30s"),
        Binding("left_bracket", "speed_down", "Slower", key_display="["),
        Binding("right_bracket", "speed_up", "Faster", key_display="]"),
    ]

    def __init__(self, episode: Episode, data_manager: DataManager, player: Player) -> None:
        super().__init__()
        self._ep = episode
        self._data = data_manager
        self._player = player

    def compose(self) -> ComposeResult:
        yield Static(id="np-title", classes="np-title")
        yield Static(id="np-progress", classes="np-progress")
        yield Static(id="np-time", classes="np-time")
        yield Static(id="np-controls", classes="np-controls")
        yield Static(id="np-description", classes="np-description")

    def on_mount(self) -> None:
        self.set_interval(0.5, self._refresh)

    def _refresh(self) -> None:
        status = self._player.get_status()
        if status is None and self._player.is_process_alive():
            live_pos, live_len = self._player.get_live_progress()
            status = PlayerStatus(True, False, live_pos, live_len)
        if status is None:
            self._render_stopped()
            return
        self._render_playing(status)

    def _render_playing(self, status: PlayerStatus) -> None:
        ep = self._ep

        # Title
        title = Text()
        title.append(f"\n  {ep.title}", style="bold")
        title.append(f"\n  ⏱ {ep.duration or '00:00:00'}", style="dim")
        self.query_one("#np-title", Static).update(title)

        # Big progress bar
        bar_width = 50
        if status.duration > 0:
            fraction = max(min(status.position / status.duration, 1.0), 0.0)
            filled = int(round(fraction * bar_width))
            pct = int(fraction * 100)
            bar = Text("  ")
            bar.append("█" * filled, style="bold green")
            bar.append("░" * (bar_width - filled), style="dim grey35")
            bar.append(f"  {pct}%", style="bold green")
            self.query_one("#np-progress", Static).update(bar)

            pos_m = int(status.position // 60)
            pos_s = int(status.position % 60)
            dur_m = int(status.duration // 60)
            dur_s = int(status.duration % 60)
            speed = self._player.get_speed()
            icon = "[ll]" if status.is_paused else "[->]"
            icon_style = "bold yellow" if status.is_paused else "bold green"
            time_text = Text(f"  {icon}  {pos_m}:{pos_s:02d} / {dur_m}:{dur_s:02d}", style=icon_style)
            if speed != 1.0:
                time_text.append(f"  [{speed}x]", style="bold cyan")
            self.query_one("#np-time", Static).update(time_text)
        else:
            self.query_one("#np-progress", Static).update("  Waiting for mpv...")
            self.query_one("#np-time", Static).update("")

        # Controls hint
        controls = Text("  [Space] Pause  [s] Stop  [←] [→] Seek  [[ ]] Speed  [Esc] Close", style="dim")
        self.query_one("#np-controls", Static).update(controls)

        # Description
        body = Text()
        if ep.summary:
            import re
            clean = re.sub(r"<[^>]+>", "", ep.summary)
            if len(clean) > 500:
                clean = clean[:500] + "\n\n… (truncated)"
            body.append(f"\n  {clean}", style="")
        self.query_one("#np-description", Static).update(body)

    def _render_stopped(self) -> None:
        self.query_one("#np-title", Static).update(Text("\n  Playback ended", style="dim"))
        self.query_one("#np-progress", Static).update("")
        self.query_one("#np-time", Static).update("")
        self.query_one("#np-controls", Static).update("")
        self.query_one("#np-description", Static).update("")

    # ── actions ───────────────────────────────────────────────

    def action_pause(self) -> None:
        self._player.toggle_pause()
        self._refresh()

    def action_stop(self) -> None:
        self._player.stop()
        self.app.pop_screen()

    def action_seek_back(self) -> None:
        self._player.seek(-30)
        self._refresh()

    def action_seek_forward(self) -> None:
        self._player.seek(30)
        self._refresh()

    def action_speed_down(self) -> None:
        speeds = self._player.SPEEDS
        cur = self._player.get_speed()
        idx = speeds.index(cur) if cur in speeds else 2
        new = speeds[idx - 1] if idx > 0 else speeds[0]
        self._player.set_speed(new)
        self._refresh()

    def action_speed_up(self) -> None:
        speeds = self._player.SPEEDS
        cur = self._player.get_speed()
        idx = speeds.index(cur) if cur in speeds else 2
        new = speeds[idx + 1] if idx < len(speeds) - 1 else speeds[-1]
        self._player.set_speed(new)
        self._refresh()

    def action_dismiss(self) -> None:
        self.app.pop_screen()


class SearchScreen(Screen[None]):
    """Cross-feed episode search.

    Collects all episodes from cached feed results and filters live by
    title as the user types.  Press ``Enter`` on a result to start
    playback immediately, then returns to the feed screen.

    Actions:
        Esc — close
    """

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
        yield Input(placeholder="Search episodes…", id="search-input")
        yield Static("Type to search — Enter to play selected result", id="search-status", classes="status")
        yield DataTable(id="search-results")
        yield Footer()

    def on_mount(self) -> None:
        # Collect all episodes from cached feeds
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

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter results as user types."""
        query = event.value.strip().lower()
        table = self.query_one("#search-results", DataTable)
        table.clear()
        if not query:
            return

        for ep in self._all_episodes:
            if query in ep.title.lower():
                # Find which feed this episode belongs to
                feed_title = ""
                for url in self._data.get_feeds():
                    cached = self._data.get_cached_result(url)
                    if cached and any(e.episode_id == ep.episode_id for e in cached.episodes):
                        feed_title = cached.title
                        break
                title_trunc = (ep.title[:47] + "…") if len(ep.title) > 47 else ep.title
                table.add_row(
                    Text(feed_title, style="dim"),
                    Text(title_trunc, style="bold"),
                    Text(EpisodeScreen._format_date(ep.published), style="dim"),
                )

    def _find_episode_by_title(self, title: str) -> Episode | None:
        """Find the first episode matching the given title (exact match for selection)."""
        for ep in self._all_episodes:
            if ep.title == title:
                return ep
        return None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Play the selected episode."""
        row_key = event.row_key
        table = self.query_one("#search-results", DataTable)
        row = table.get_row(row_key)
        if not row or len(row) < 2:
            return
        feed_title = row[0].plain if hasattr(row[0], 'plain') else str(row[0])
        # Find matching episode
        for ep in self._all_episodes:
            for url in self._data.get_feeds():
                cached = self._data.get_cached_result(url)
                if cached and cached.title == feed_title and ep.episode_id:
                    if any(e.episode_id == ep.episode_id for e in cached.episodes):
                        self._play_episode(ep)
                        return

    def _play_episode(self, episode: Episode) -> None:
        """Play an episode via Player."""
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
            self.notify(f"▶ {episode.title}", severity="information", timeout=3)
            self.app.pop_screen()

    def action_dismiss(self) -> None:
        self.app.pop_screen()


class EpisodeDetailScreen(Screen[None]):
    """Modal overlay showing full episode metadata — description, link, date, duration.

    Strips HTML tags from the RSS summary for clean terminal display and
    truncates descriptions longer than 2000 characters.

    Actions:
        Esc / Enter / Space / q — close
    """

    BINDINGS = [
        Binding("escape,enter,q,space", "dismiss", "Close"),
    ]

    def __init__(self, episode: Episode) -> None:
        super().__init__()
        self._ep = episode

    def compose(self) -> ComposeResult:
        yield Static("", id="detail-header", classes="dialog-title")
        yield Static("", id="detail-body")
        yield Static("Esc / Enter to close", id="detail-footer", classes="status")

    def on_mount(self) -> None:
        ep = self._ep

        header = Text()
        header.append("📄 ", style="bold cyan")
        header.append(ep.title, style="bold")
        self.query_one("#detail-header", Static).update(header)

        body = Text()

        # Published date
        if ep.published:
            body.append(f"  📅 {EpisodeScreen._format_date(ep.published)}", style="dim")
            body.append("\n", style="")

        # Duration
        if ep.duration:
            body.append(f"  ⏱ {ep.duration}", style="dim")
            body.append("\n", style="")

        # Link
        if ep.url:
            body.append(f"  🔗 {ep.url}", style="dim")
            body.append("\n\n", style="")

        # Summary / description — strip HTML tags for clean display
        if ep.summary:
            clean = re.sub(r"<[^>]+>", "", ep.summary)
            # Truncate if very long
            if len(clean) > 2000:
                clean = clean[:2000] + "\n\n… (truncated)"
            body.append(clean, style="")
        else:
            body.append("  (No description)", style="dim")

        self.query_one("#detail-body", Static).update(body)

    def action_dismiss(self) -> None:
        self.app.pop_screen()


class HelpScreen(Screen[None]):
    """Modal overlay showing context-sensitive keybindings.

    Displays a Rich-styled table of keybindings for the current screen
    (Feed or Episode), plus general tips for sorting, scrubbing, and
    theme toggling.  Press any key to dismiss.
    """

    BINDINGS = [
        Binding("escape,space,enter,q,question_mark", "dismiss", "Close", key_display="Esc"),
    ]

    _BINDINGS_BY_SCREEN = {
        "Feed": [
            ("a", "Add a feed URL"),
            ("i", "Import OPML file"),
            ("e", "Export OPML file"),
            ("u", "Refresh all feeds"),
            ("/", "Search episodes"),
            ("r", "Remove selected feed"),
            ("Enter", "Browse episodes"),
            ("q", "Quit AetherPod"),
            ("?", "Show this help"),
        ],
        "Episode": [
            ("Esc", "Go back / Exit scrub mode"),
            ("Enter", "Play selected episode"),
            ("Space", "Toggle pause / resume (global)"),
            ("s", "Stop playback"),
            ("m", "Mark played / unplayed"),
            ("r", "Restart from beginning"),
            ("d", "Show episode details"),
            ("N", "Now-playing full-screen view"),
            ("u", "Full refresh (no date limit)"),
            ("f", "Toggle unplayed-only filter"),
            ("← / →", "Seek -30s / +30s (5s in scrub mode)"),
            ("Ctrl+← / Ctrl+→", "Seek -1s / +1s"),
            ("[ / ]", "Speed down / up (0.5x–3.0x)"),
            (".", "Toggle scrub mode (click timeline to seek)"),
            ("a", "Add to play queue"),
            ("A", "Play next (stop current, play selected)"),
            ("v", "View play queue"),
            ("t", "Toggle dark/light theme"),
            ("q", "Quit AetherPod"),
            ("?", "Show this help"),
        ],
        "Feed": [
            ("a", "Add a feed URL"),
            ("i", "Import OPML file"),
            ("e", "Export OPML file"),
            ("u", "Refresh all feeds"),
            ("/", "Search episodes"),
            ("r", "Remove selected feed"),
            ("Enter", "Browse episodes"),
            ("Space", "Toggle pause / resume (global)"),
            ("t", "Toggle dark/light theme"),
            ("q", "Quit AetherPod"),
            ("?", "Show this help"),
        ],
    }

    def __init__(self, screen_name: str = "Feed") -> None:
        super().__init__()
        self._screen_name = screen_name

    def compose(self) -> ComposeResult:
        yield Static("", id="help-header", classes="dialog-title")
        yield Static("", id="help-content")
        yield Static("Press Esc or ? to close", id="help-footer",
                      classes="status")
        yield Static("", id="help-stack", classes="status")

    def on_mount(self) -> None:
        from src import __version__

        header = Text()
        header.append("📖 ", style="bold cyan")
        header.append(f"{self._screen_name} Screen Keybindings", style="bold")
        self.query_one("#help-header", Static).update(header)

        bindings = self._BINDINGS_BY_SCREEN.get(self._screen_name, [])
        content = Text()
        for key, desc in bindings:
            content.append(f"  {key:<20}", style="bold cyan")
            content.append(f"  {desc}\n", style="")

        content.append("\n", style="")
        tips = [
            ("Click column headers", "to sort (3-state cycle)"),
            ("Click timeline bar", "to seek (scrub mode)"),
            ("t", "toggle dark/light theme"),
        ]
        for key, desc in tips:
            content.append(f"  {key:<20}", style="bold cyan")
            content.append(f"  {desc}\n", style="dim")
        self.query_one("#help-content", Static).update(content)

        stack = Text(
            f"AetherPod v{__version__}  │  Python 3.14+  │  Textual  │  GPLv3",
            style="dim",
        )
        self.query_one("#help-stack", Static).update(stack)

    def action_dismiss(self) -> None:
        self.app.pop_screen()


class SplashScreen(Screen):
    """Startup splash — ASCII logo + fastfetch-style system info, auto-dismisses."""

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
        from src.splash import SplashRenderable
        import shutil

        mpv_ok = shutil.which("mpv") is not None
        splash = SplashRenderable(self._n_feeds, self._n_played, mpv_ok)
        yield Static(splash, id="splash-content")
        yield Label("  Press any key or wait…  ", id="splash-hint")

    def on_mount(self) -> None:
        self.title = ""
        self._timer = self.set_timer(4, self._auto_dismiss)

    def action_dismiss(self) -> None:
        if self._timer is not None:
            self._timer.reset()
            self._timer = None
        self.app.pop_screen()
        self.app.push_screen(FeedScreen(self._data, self._player))

    def _auto_dismiss(self) -> None:
        self._timer = None
        self.action_dismiss()


class QueueScreen(Screen):
    """Displays and manages the play queue."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("enter", "play", "Play", priority=True),
        Binding("d", "remove", "Remove"),
        Binding("c", "clear", "Clear"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, data_manager: DataManager, player: Player) -> None:
        super().__init__()
        self._data = data_manager
        self._player = player

    def compose(self) -> ComposeResult:
        yield Header()
        yield ListView(id="queue-list")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        queue = self._player.get_queue()
        feed_list = self.query_one("#queue-list", ListView)
        feed_list.clear()

        if not queue:
            feed_list.append(ListItem(Label("Queue is empty — press Esc to go back")))
            self.sub_title = "0 queued"
            return

        self.sub_title = f"{len(queue)} queued"
        for idx, (url, eid, title) in enumerate(queue):
            # Try to find the feed name from cache
            feed_name = ""
            for feed_url in self._data.get_feeds():
                cached = self._data.get_cached_result(feed_url)
                if cached:
                    for ep in cached.episodes:
                        if ep.episode_id == eid or ep.url == url:
                            feed_name = cached.title
                            break
                if feed_name:
                    break
            label = Label(f"{title}")
            if feed_name:
                label = Label(f"{title}  — {feed_name}")
            item = ListItem(label)
            item._queue_index = idx  # type: ignore[attr-defined]
            feed_list.append(item)

    def action_back(self) -> None:
        self.app.pop_screen()

    async def action_play(self) -> None:
        feed_list = self.query_one("#queue-list", ListView)
        if not feed_list.index:
            return
        item = feed_list.children[feed_list.index]
        idx = getattr(item, "_queue_index", None)
        if idx is None:
            return
        queue = self._player.get_queue()
        if idx < 0 or idx >= len(queue):
            return
        url, eid, title = queue[idx]
        # Remove from queue and play
        self._player.remove_from_queue(idx)
        self._player.stop()

        # Build an Episode-like object to play
        from src.engine import Episode
        ep = Episode(title=title, url=url, episode_id=eid)
        # Find the episodescreen to delegate play
        for screen in self.app.screen_stack:
            if isinstance(screen, EpisodeScreen):
                await screen._do_play(ep)
                break
        self._refresh()

    def action_remove(self) -> None:
        feed_list = self.query_one("#queue-list", ListView)
        if feed_list.index is None:
            return
        item = feed_list.children[feed_list.index]
        idx = getattr(item, "_queue_index", None)
        if idx is not None:
            self._player.remove_from_queue(idx)
            self._refresh()

    def action_clear(self) -> None:
        self._player.clear_queue()
        self._refresh()

    def action_quit(self) -> None:
        self.app.exit()
