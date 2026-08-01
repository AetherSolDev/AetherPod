# Created: 2026-07-25
# Last Edited: 2026-08-01 03:17 CT (America/Chicago)
# Path: aetherpod/splash.py
# Purpose: Startup splash screen — ASCII logo, app stats, and features list.

from __future__ import annotations

import logging

from rich.console import Console, ConsoleOptions, RenderResult
from rich.table import Table
from rich.text import Text

from aetherpod import __version__

logger = logging.getLogger(__name__)

# Theme colors (from aetherpod/theme.py dark palette)
BG = "#1a1a2e"
BLUE = "#A78BFA"
ORANGE = "#FB923C"
GREEN = "#22C55E"
FG = "#e8e8e8"
MUTED = "#b0b0c0"
BORDER = "#555577"
FEATURES_RED = "#ff6b6b"

AETHER_LOGO = r"""
╔══════════════════════════════╗
║       A E T H E R P O D      ║
║   Terminal Podcast Manager   ║
╚══════════════════════════════╝
"""

FEATURES = [
    "Subscribe to any RSS/Atom podcast feed",
    "Browse episodes in a sortable DataTable",
    "Live progress bars during playback",
    "Play / pause / seek / speed control",
    "Cross-feed search",
    "OPML import / export",
    "Dark / light theme toggle",
    "Resume playback where you left off",
    "Async feed refresh \u2014 instant cache",
]


def _empty() -> Text:
    return Text("  ", style=f"on {BG}")


def _val(label: str, value: str, accent: str = GREEN) -> Text:
    return Text.assemble(
        Text(f"  {label}: ", style=f"{ORANGE} on {BG}"),
        Text(value, style=f"{accent} on {BG}"),
    )


class SplashRenderable:
    def __init__(self, n_feeds: int, n_played: int, mpv_ok: bool) -> None:
        self._n_feeds = n_feeds
        self._n_played = n_played
        self._mpv_ok = mpv_ok

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        logo_lines = AETHER_LOGO.strip("\n").split("\n")
        logo_width = max(len(l) for l in logo_lines) if logo_lines else 0

        right_lines: list[Text] = [
            Text(f"  AetherPod v{__version__}", style=f"bold {BLUE} on {BG}"),
            _empty(),
            Text("  Terminal podcast manager for Arch Linux", style=f"italic {MUTED} on {BG}"),
            _empty(),
            _val("Feeds", str(self._n_feeds)),
            _val("Played", str(self._n_played)),
            _val("mpv", "detected" if self._mpv_ok else "NOT FOUND",
                 GREEN if self._mpv_ok else "#EF4444"),
            _empty(),
            Text("  Features:", style=f"bold {FEATURES_RED} on {BG}"),
        ]

        for f in FEATURES:
            right_lines.append(Text(f"  \u2022 {f}", style=f"{FG} on {BG}"))

        right_lines.append(_empty())
        right_lines.append(
            Text("  Python 3.14+  \u00b7  Textual  \u00b7  feedparser  \u00b7  mpv",
                 style=f"dim {MUTED} on {BG}")
        )

        rh = len(right_lines)
        logo_h = len(logo_lines)
        pad_top = (rh - logo_h) // 2
        pad_bot = rh - logo_h - pad_top
        left_padded = (
            [Text(" " * logo_width, style=f"on {BG}")] * pad_top
            + [Text(l, style=f"{BLUE} on {BG}") for l in logo_lines]
            + [Text(" " * logo_width, style=f"on {BG}")] * pad_bot
        )

        table = Table.grid(expand=False, padding=0)
        table.add_column("left", justify="center", width=logo_width + 2)
        table.add_column("sep", justify="center", width=3)
        table.add_column("right", justify="left", width=56)

        for i in range(rh):
            left_cell = (
                left_padded[i]
                if i < len(left_padded)
                else Text(" " * logo_width, style=f"on {BG}")
            )
            sep = Text(f" \u2502 ", style=f"bold {BORDER} on {BG}")
            table.add_row(left_cell, sep, right_lines[i])

        yield table
