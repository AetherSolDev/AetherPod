# Created: 2026-07-27
# Last Edited: 2026-08-01 03:18 CT (America/Chicago)
# Path: aetherpod/screens/now_playing.py
# Purpose: Full-screen now-playing view with big progress bar, metadata, controls.

from __future__ import annotations

import re

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static

from aetherpod.engine import DataManager
from aetherpod.engines import PlayerStatus
from aetherpod.models import Episode
from aetherpod.player import Player


class NowPlayingScreen(Screen[None]):
    BINDINGS = [
        Binding("escape,n", "dismiss", "Close"),
        Binding("space", "pause", "Pause"),
        Binding("s", "stop", "Stop"),
        Binding("left", "seek_back", "-30s"),
        Binding("right", "seek_forward", "+30s"),
        Binding("left_bracket", "speed_down", "Slower", key_display="["),
        Binding("right_bracket", "speed_up", "Faster", key_display="]"),
        Binding("1", "eq_off", "EQ:Off", key_display="1"),
        Binding("2", "eq_bright", "EQ:Bright", key_display="2"),
        Binding("3", "eq_warm", "EQ:Warm", key_display="3"),
        Binding("4", "eq_balanced", "EQ:Balanced", key_display="4"),
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

        title = Text()
        title.append(f"\n  {ep.title}", style="bold")
        title.append(f"\n  \u23f1 {ep.duration or '00:00:00'}", style="dim")
        self.query_one("#np-title", Static).update(title)

        bar_width = 50
        if status.duration > 0:
            fraction = max(min(status.position / status.duration, 1.0), 0.0)
            filled = int(round(fraction * bar_width))
            pct = int(fraction * 100)
            bar = Text("  ")
            bar.append("\u2588" * filled, style="bold green")
            bar.append("\u2591" * (bar_width - filled), style="dim grey35")
            bar.append(f"  {pct}%", style="bold green")
            self.query_one("#np-progress", Static).update(bar)

            pos_m = int(status.position // 60)
            pos_s = int(status.position % 60)
            dur_m = int(status.duration // 60)
            dur_s = int(status.duration % 60)
            speed = self._player.get_speed()
            icon = "[ll]" if status.is_paused else "[\u2013>]"
            icon_style = "bold yellow" if status.is_paused else "bold green"
            time_text = Text(
                f"  {icon}  {pos_m}:{pos_s:02d} / {dur_m}:{dur_s:02d}",
                style=icon_style,
            )
            if speed != 1.0:
                time_text.append(f"  [{speed}x]", style="bold cyan")
            self.query_one("#np-time", Static).update(time_text)
        else:
            self.query_one("#np-progress", Static).update("  Waiting for mpv...")
            self.query_one("#np-time", Static).update("")

        _, eq_label = self._player.get_eq_preset()
        eq_display = f"  EQ:{eq_label}" if eq_label != "Off" else ""
        controls = Text(
            f"  [Space] Pause  [s] Stop  [\u2190] [\u2192] Seek"
            f"  [[ ]] Speed  [1-4] EQ{eq_display}  [Esc] Close",
            style="dim",
        )
        self.query_one("#np-controls", Static).update(controls)

        body = Text()
        if ep.summary:
            clean = re.sub(r"<[^>]+>", "", ep.summary)
            if len(clean) > 500:
                clean = clean[:500] + "\n\n\u2026 (truncated)"
            body.append(f"\n  {clean}", style="")
        self.query_one("#np-description", Static).update(body)

    def _render_stopped(self) -> None:
        self.query_one("#np-title", Static).update(Text("\n  Playback ended", style="dim"))
        self.query_one("#np-progress", Static).update("")
        self.query_one("#np-time", Static).update("")
        self.query_one("#np-controls", Static).update("")
        self.query_one("#np-description", Static).update("")

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

    def action_eq_off(self) -> None:
        self._player.set_eq_preset(0)
        self._refresh()

    def action_eq_bright(self) -> None:
        self._player.set_eq_preset(1)
        self._refresh()

    def action_eq_warm(self) -> None:
        self._player.set_eq_preset(2)
        self._refresh()

    def action_eq_balanced(self) -> None:
        self._player.set_eq_preset(3)
        self._refresh()

    def action_dismiss(self) -> None:
        self.app.pop_screen()
