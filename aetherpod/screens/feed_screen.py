# Created: 2026-07-19
# Last Edited: 2026-07-27 15:54 CT (America/Chicago)
# Path: aetherpod/screens/feed_screen.py
# Purpose: Feed subscription list screen — main entry screen for AetherPod.

from __future__ import annotations

import asyncio
import logging

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView

from aetherpod.engine import DataManager
from aetherpod.models import FeedResult
from aetherpod.player import Player
from aetherpod.rss import fetch_feed_async
from aetherpod.screens.dialogs import AddFeedDialog, PathInputDialog
from aetherpod.screens.detail_help import HelpScreen
from aetherpod.screens.episode_screen import EpisodeScreen
from aetherpod.screens.search import SearchScreen
from aetherpod.widgets import LoadingSpinner

logger = logging.getLogger(__name__)


class FeedScreen(Screen):
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
        self._render_from_cache()
        asyncio.create_task(self._refresh_feeds())

    def action_add_feed(self) -> None:
        def _on_url(url: str | None) -> None:
            if url:
                if self._data.add_feed(url):
                    self.notify("Feed added", severity="information", timeout=3)
                else:
                    self.notify("Feed already subscribed", severity="warning", timeout=3)
                asyncio.create_task(self._refresh_feeds())

        self.app.push_screen(AddFeedDialog(), _on_url)

    async def action_refresh(self) -> None:
        await self._refresh_feeds()

    def action_remove_feed(self) -> None:
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
        if self._player.is_playing():
            self._player.stop()
        self.app.exit()

    def action_import_opml(self) -> None:
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
        def _on_path(path: str | None) -> None:
            if path:
                count = self._data.opml_export(path)
                if count > 0:
                    self.notify(f"Exported {count} feed(s)", severity="information", timeout=3)
                else:
                    self.notify("No feeds to export", severity="warning", timeout=3)

        self.app.push_screen(
            PathInputDialog("Export OPML", "aetherpod_subscriptions.opml"), _on_path
        )

    def action_search(self) -> None:
        self.app.push_screen(SearchScreen(self._data, self._player))

    def action_show_help(self) -> None:
        self.app.push_screen(HelpScreen(screen_name="Feed"))

    _last_playing_feed: str = ""

    def _update_playing_indicator(self, playing_feed_url: str) -> None:
        if playing_feed_url != self._last_playing_feed:
            self._last_playing_feed = playing_feed_url
            self._render_from_cache()

    def _render_from_cache(self) -> None:
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
            item._feed_url = url
            item._feed_result = cached
            if cached is not None:
                has_cache = True
                total = len(cached.episodes)
                                    played = sum(
                        1 for e in cached.episodes
                        if self._data.is_played(e.episode_id or "")
                    )
                unplayed = total - played
                prefix = "\u25b6 " if url == playing_feed_url else ""
                                    label = Label(
                        f"{prefix}{cached.title}  ({total} ep, {unplayed} new)"
                    )
            else:
                label = Label(f"  {url}  (waiting...)")
            item.compose_add_child(label)
            feed_list.append(item)

        if urls:
            if has_cache:
                self._start_spinner(
                    f"{len(urls)} feed{'s' if len(urls) != 1 else ''}"
                    " \u2014 refreshing..."
                )
            else:
                self._start_spinner(
                    f"{len(urls)} feed{'s' if len(urls) != 1 else ''}"
                    " \u2014 loading..."
                )

    async def _refresh_feeds(self) -> None:
        urls = self._data.get_feeds()
        feed_list = self.query_one("#feed-list", ListView)

        if not urls:
            return

        self._start_spinner(f"Refreshing {len(urls)} feed(s)...")

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

        try:
            feed_list.clear()
        except ValueError:
            logger.debug("Ignored ListView hover race during refresh")
        for url, result in zip(urls, results):
            item = ListItem()
            item._feed_url = url

            playing_feed_url = (
                self._player.get_current_feed_url() if self._player.is_playing() else ""
            )
            prefix = "\u25b6 " if url == playing_feed_url else ""

            if isinstance(result, Exception):
                logger.warning("Feed fetch exception for %s: %s", url, result)
                item._feed_result = None
                label = Label(f"{prefix}\u2717 {url} \u2014 {result}")
            elif result.not_modified:
                cached = self._data.get_cached_result(url)
                item._feed_result = cached
                if cached:
                    total = len(cached.episodes)
                                        played = sum(
                        1 for e in cached.episodes
                        if self._data.is_played(e.episode_id or "")
                    )
                    unplayed = total - played
                    label = Label(
                        f"{prefix}{cached.title}  ({total} ep, {unplayed} new)"
                    )
                else:
                    label = Label(f"{prefix}  {url}  (unchanged)")
            elif result.error:
                cached = self._data.get_cached_result(url)
                item._feed_result = cached
                if cached:
                    total = len(cached.episodes)
                    played = sum(
                        1 for e in cached.episodes
                        if self._data.is_played(e.episode_id or "")
                    )
                    unplayed = total - played
                    label = Label(
                        f"{prefix}\u26a0 {cached.title}"
                        f"  ({total} ep, {unplayed} new)  \u2014 {result.error}"
                    )
                else:
                    label = Label(f"{prefix}\u2717 {url} \u2014 {result.error}")
            else:
                if result.etag or result.last_modified:
                    self._data.save_feed_headers(url, result.etag, result.last_modified)
                self._data.save_cached_result(url, result)
                item._feed_result = result
                total = len(result.episodes)
                played = sum(
                    1 for e in result.episodes
                    if self._data.is_played(e.episode_id or "")
                )
                unplayed = total - played
                label = Label(f"{prefix}{result.title}  ({total} ep, {unplayed} new)")

            item.compose_add_child(label)
            feed_list.append(item)

        n = len(urls)
        self._set_status(f"{n} feed{'s' if n != 1 else ''} \u2014 'a' to add, Enter to browse")

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
        item = event.item
        result: FeedResult | None = getattr(item, "_feed_result", None)
        url: str | None = getattr(item, "_feed_url", None)
        if result is not None and result.error:
            self._set_status(f"\u2717 {result.error}")
            self.notify(f"Cannot browse: {result.error}", severity="error", timeout=4)
        elif result is not None and result.episodes:
            self.app.push_screen(EpisodeScreen(result, url, self._data, self._player))
        elif result is not None:
            self._set_status(f"No episodes in '{result.title}'")
        else:
            self._set_status("No data for this feed")
