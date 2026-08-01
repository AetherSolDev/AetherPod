# Created: 2026-07-24
# Last Edited: 2026-08-01 03:18 CT (America/Chicago)
# Path: aetherpod/theme.py
# Purpose: Custom Textual themes — dark navy + blue/teal palette and light variant.

from __future__ import annotations

from textual.theme import Theme

AETHERPOD_DARK = Theme(
    name="aetherpod-dark",
    primary="#54a0ff",
    secondary="#00d2d3",
    accent="#54a0ff",
    warning="#ff9f43",
    error="#ff6b6b",
    success="#4CAF50",
    foreground="#e8e8e8",
    background="#1a1a2e",
    surface="#1a1a2e",
    panel="#2d2d44",
    boost="#3d3d5c",
    dark=True,
    variables={
        "text-muted": "#b0b0c0",
        "border": "#555577",
        "playing": "#00d2d3",
        "paused": "#ff9f43",
    },
)

AETHERPOD_LIGHT = Theme(
    name="aetherpod-light",
    primary="#54a0ff",
    secondary="#00d2d3",
    accent="#54a0ff",
    warning="#FF9800",
    error="#ff5555",
    success="#4CAF50",
    foreground="#2f3542",
    background="#f8f9fa",
    surface="#f8f9fa",
    panel="#ffffff",
    boost="#f1f2f6",
    dark=False,
    variables={
        "text-muted": "#636e72",
        "border": "#ced6e0",
        "playing": "#00d2d3",
        "paused": "#ff9f43",
    },
)

THEMES = {
    "aetherpod-dark": AETHERPOD_DARK,
    "aetherpod-light": AETHERPOD_LIGHT,
}
