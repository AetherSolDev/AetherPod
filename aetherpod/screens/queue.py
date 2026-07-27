# Created: 2026-07-27
# Last Edited: 2026-07-27 15:54 CT (America/Chicago)
# Path: aetherpod/screens/queue.py
# Purpose: Play queue management screen — view, remove, clear, play queued episodes.

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView

from aetherpod.engine import DataManager
from aetherpod.models import Episode
from aetherpod.player import Player


class QueueScreen(Screen):
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
            feed_list.append(ListItem(Label("Queue is empty \u2014 press Esc to go back")))
            self.sub_title = "0 queued"
            return

        self.sub_title = f"{len(queue)} queued"
        for idx, (url, eid, title) in enumerate(queue):
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
                label = Label(f"{title}  \u2014 {feed_name}")
            item = ListItem(label)
            item._queue_index = idx
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
        self._player.remove_from_queue(idx)
        self._player.stop()

        from aetherpod.screens.episode_screen import EpisodeScreen
        ep = Episode(title=title, url=url, episode_id=eid)
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
