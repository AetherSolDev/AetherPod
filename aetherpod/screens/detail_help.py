# Created: 2026-07-27
# Last Edited: 2026-08-01 11:41 CT (America/Chicago)
# Path: aetherpod/screens/detail_help.py
# Purpose: Modal overlays — EpisodeDetailScreen and HelpScreen.

from __future__ import annotations

import re

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static

from aetherpod.models import Episode
from aetherpod.screens.helpers import format_date


class EpisodeDetailScreen(Screen[None]):
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
        header.append("\U0001f4c4 ", style="bold cyan")
        header.append(ep.title, style="bold")
        self.query_one("#detail-header", Static).update(header)

        body = Text()

        if ep.published:
            body.append(f"  \U0001f4c5 {format_date(ep.published)}", style="dim")
            body.append("\n", style="")

        if ep.duration:
            body.append(f"  \u23f1 {ep.duration}", style="dim")
            body.append("\n", style="")

        if ep.url:
            body.append(f"  \U0001f517 {ep.url}", style="dim")
            body.append("\n\n", style="")

        if ep.summary:
            clean = re.sub(r"<[^>]+>", "", ep.summary)
            if len(clean) > 2000:
                clean = clean[:2000] + "\n\n\u2026 (truncated)"
            body.append(clean, style="")
        else:
            body.append("  (No description)", style="dim")

        self.query_one("#detail-body", Static).update(body)

    def action_dismiss(self) -> None:
        self.app.pop_screen()


class HelpScreen(Screen[None]):
    BINDINGS = [
        Binding("escape,space,enter,q,question_mark", "dismiss", "Close", key_display="Esc"),
    ]

    _BINDINGS_BY_SCREEN = {
        "Feed": [
            ("a", "Add a feed URL"),
            ("i", "Import OPML file"),
            ("e", "Export OPML file"),
            ("u", "Refresh all feeds"),
            ("s", "Sort feeds: subscribe order \u2194 A\u2192Z \u2194 Z\u2192A"),
            ("f", "Filter feeds by name"),
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
            ("\u2190 / \u2192", "Seek -30s / +30s (5s in scrub mode)"),
            ("Ctrl+\u2190 / Ctrl+\u2192", "Seek -1s / +1s"),
            ("[ / ]", "Speed down / up (0.5x\u20133.0x)"),
            (".", "Toggle scrub mode (click timeline to seek)"),
            ("a", "Add to play queue"),
            ("A", "Play next (stop current, play selected)"),
            ("v", "View play queue"),
            ("1 / 2 / 3 / 4", "EQ presets: Off / Bright / Warm / Balanced"),
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
        yield Static("Press Esc or ? to close", id="help-footer", classes="status")
        yield Static("", id="help-stack", classes="status")

    def on_mount(self) -> None:
        from aetherpod import __version__

        header = Text()
        header.append("\U0001f4d6 ", style="bold cyan")
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
            f"AetherPod v{__version__}  \u2502  Python 3.14+  \u2502  Textual  \u2502  GPLv3",
            style="dim",
        )
        self.query_one("#help-stack", Static).update(stack)

    def action_dismiss(self) -> None:
        self.app.pop_screen()
