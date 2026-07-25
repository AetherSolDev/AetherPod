# Created: 2026-07-19
# Last Edited: 2026-07-25 17:28 CT (America/Chicago)
# Path: docs/sys/ARCHITECTURE.md
# Purpose: High-level component map and design rationale for AetherPod.

# AetherPod Architecture

```
AetherPod/
├── aetherpod.py                # CLI entry point (thin wrapper)
├── pyproject.toml              # Package metadata + console_scripts
├── requirements.txt            # aiohttp, feedparser, textual
├── README.md
├── LICENSE                     # GPLv3
├── assets/
│   └── screens/                # Screenshots for README
├── src/
│   ├── __init__.py             # Version
│   ├── app.py                  # AetherPod App — CSS, screens, 1s poll
│   ├── cli.py                  # CLI logic (argparse, upgrade, logging)
│   ├── engine.py               # DataManager + RSS fetch (sync + async)
│   ├── player.py               # MpvPlayer + play queue + auto-download cache
│   ├── screens.py              # All screens (Feed, Episode, Queue, Splash, etc.)
│   ├── splash.py               # Splash renderable
│   ├── theme.py                # Dark/light Theme definitions
│   └── widgets.py              # LoadingSpinner
├── data/
│   └── state.json              # Runtime state (~/.local/state/aetherpod/state.json)
└── docs/
    ├── HELP.md                 # User keybinding reference
    ├── INSTALL.md              # Installation guide
    └── sys/                    # Internal planning docs
        ├── CHANGELOG.md
        ├── ARCHITECTURE.md
        └── aetherpod.mmd       # Mermaid architecture diagram
```

## Component Responsibilities

| Component | File | Responsibility |
|---|---|---|---|
| **aetherpod.py** | Entry point | Thin wrapper, delegates to `src.cli.main()` |
| **pyproject.toml** | Meta | Package metadata, deps, console_scripts entry point |
| **AetherPod** | `src/app.py` | Textual App subclass, CSS, mounts SplashScreen, 1s poll, global pause, theme toggle |
| **src/cli.py** | CLI | Argument parsing, logging setup, headless commands, `--upgrade` |
| **DataManager** | `src/engine.py` | JSON state persistence, feed/played-episode CRUD, OPML import/export, configurable refresh_days |
| **fetch_feed** / **fetch_feed_async** | `src/engine.py` | sync + async RSS/Atom parsing, conditional GET (ETag/Last-Modified) |
| **SplashScreen** | `src/screens.py` | Branded startup splash with ASCII logo, stats, features, stack info |
| **FeedScreen** | `src/screens.py` | Feed list, add/remove/refresh, now-playing indicator (▶) |
| **EpisodeScreen** | `src/screens.py` | Episode DataTable, play/pause/seek/stop/speed, progress bars, play queue, scrub |
| **NowPlayingScreen** | `src/screens.py` | Full-screen playback view with large progress bar and controls |
| **QueueScreen** | `src/screens.py` | Play queue management (view, remove, clear, play) |
| **SearchScreen** | `src/screens.py` | Cross-feed search (`/` key) |
| **EpisodeDetailScreen** | `src/screens.py` | Modal episode detail popup |
| **HelpScreen** | `src/screens.py` | Modal keybinding reference with stack info footer |
| **SplashRenderable** | `src/splash.py` | Rich renderable — ASCII logo + stats + features, theme colors |
| **ThemeManager** | `src/theme.py` | Dark/light CSS variable maps |
| **LoadingSpinner** | `src/widgets.py` | Braille spinner renderable |
| **MpvPlayer** | `src/player.py` | Subprocess mpv, IPC control, play queue, auto-download cache, cleanup |

## state.json Schema

```json
{
  "version": 1,
  "feeds": ["https://...rss", "https://...rss"],
  "played_episodes": ["ep_id_1", "ep_id_2"],
  "episode_progress": {
    "ep_id_1": {"position": 123.5, "total_length": 3600.0}
  }
}
```

- **version** *(planned, Phase 9.3)* — schema version integer for automatic state migration. Absent on legacy files; `DataManager.state_load()` will detect versions < current and run migration functions.
- **feeds** — ordered list of subscribed RSS feed URLs.
- **played_episodes** — ordered list of episode IDs (most recent last). Doubles as the source of truth for what's played and the order for retention trimming.
- **episode_progress** — optional dict mapping episode IDs to playback position data. Present only for partially-listened episodes.

## Data Flow

```
User Input → main.py → AetherPod → FeedScreen → DataManager (state.json)
                                    → fetch_feed_async (aiohttp/RSS)
                                    → EpisodeScreen → MpvPlayer (mpv IPC)
                                    → NowPlayingScreen (full-screen playback)
                                    → SearchScreen (cross-feed search)
                                    → EpisodeDetailScreen (detail popup)
                                                                  ↓
                                                   _wait_loop (thread, stdout parse)
                                                   ├── _live_position / _live_duration
                                                   │   (published every ~1s for UI)
                                                   └── exit callback → DataManager.save_progress()
                                                                  ↓
                                                   (on exit) → EpisodeScreen._populate()
                                                                  ↑
                                             AetherPod.set_interval(1s) ┘
                                             _poll_playback → EpisodeScreen
                                                             ._update_playback_progress()
                                                             ._refresh_playing_item()
                                                             (updates progress bar + status bar
                                                              via get_live_progress())

OPML files → DataManager.opml_import() → state.json
state.json → DataManager.opml_export() → OPML file
```

## Key Design Decisions

1. **Module-level fetch_feed** instead of a class — stateless, testable, no lifecycle to manage.
2. **DataManager uses load-then-save pattern** — simple, correct for single-process use.
3. **Screens receive DataManager reference** — no global state, screens are testable in isolation.
4. **MpvPlayer runs mpv in a thread** — non-blocking TUI, mpv manages its own window/audio.
5. **urllib-based RSS fetch** (not feedparser's built-in fetch) — allows setting a 15s timeout and catching HTTP/URL/Timeout errors before parsing, preventing hangs on dead feeds.
6. **Script-relative state path** — `main.py` resolves `data/state.json` relative to its own directory via `__file__`, so the app works from any CWD or USB mount point.
7. **Client-side unplayed filter** — toggling `_show_unplayed_only` filters the already-fetched episode list; no re-fetch needed, instant toggle.
8. **OPML via stdlib xml.etree** — no extra dependency for OPML import/export; handles standard OPML 1.0/2.0 outline structures.
9. **Import appends, export replaces** — `opml_import` adds new feeds without removing existing ones; `opml_export` writes a full OPML 2.0 document from current state.
10. **Progress captured via `--term-status-msg`** — mpv emits `POS= LEN=` on stdout/stderr; `_wait_loop` parses the last line before exit, avoiding polling or IPC.
11. **Rolling retention (MAX_PLAYED = 50)** — `DataManager._enforce_retention()` drops the oldest played entries when the list exceeds 50, keeping `state.json` small over time.
12. **Completion heuristic** — `save_progress` auto-marks an episode played when position is within 5 seconds of total_length, avoiding a separate "finished" signal.
13. **Thread-safe DataManager** — all public methods acquire `_lock` so `_wait_loop` can safely call `save_progress` from the mpv daemon thread.
14. **aiohttp-based async fetch** — `fetch_feed_async()` mirrors `fetch_feed()` but uses `aiohttp.ClientSession` with `asyncio`, keeping the TUI event loop unblocked during feed refreshes.
15. **Inline Unicode-block progress bar** — replaced the earlier `RichProgressBar` (block-level, forced its own line) with Unicode block characters (`█`/`░`) inside a single `Text` object. Each episode row is now a single line: `[✓] Title  2026-07-19  ██████░░░░  [12:34]`, keeping the list compact and aligned without table markup.
16. **Programmatic Rich Text styling for status icons** — `Text(" [->]", style="bold green")` for playing, `Text(" [ll]", style="bold yellow")` for paused, using Rich `Text` objects with `style=` parameters instead of raw markup strings to prevent tag leakage in the terminal.
17. **1s interval polling for live progress** — `AetherPod.set_interval(1, _poll_playback)` walks the screen stack every second, finds an active `EpisodeScreen`, and calls `_update_playback_progress()` to refresh the inline progress bar and status-bar position/duration text without rebuilding the entire episode list.
18. **DataTable replaces ListView in EpisodeScreen** — fixed-width columns (Status, Title, Date, Progress, Duration) guarantee perfect vertical alignment. `Bar` renderable is placed directly in the Progress cell with dedicated space, never jittering. `action_quit` in both screens now calls `self._player.stop()` before `self.app.exit()` to kill zombie mpv processes.
19. **Live progress via `_live_position`/`_live_duration` on MpvPlayer** — `_wait_loop` parses mpv's `--term-status-msg` output every ~1s and stores the latest position+duration on the player instance under `self._lock`. The 1s polling in `EpisodeScreen._update_playback_progress` calls `get_live_progress()` to read these values, so the progress bar and status bar timer remain live throughout playback rather than relying solely on the exit callback to `state.json`.
20. **Keyboard-based column width adjustment** — `Ctrl+Left`/`Ctrl+Right` adjust the Title column width in 4-char steps (range 20–80), giving the user manual control over how much of each episode title is visible.
21. **Fixed Title column width** — Changed from `width=None` (auto-fill) to `width=42` to prevent Textual from fighting manual column width changes.
22. **Scrub mode with variable-step seeking** — `.` toggles scrub mode during playback. In scrub mode, `left`/`right` seek by 5s (vs 30s normal) for fine-grained control, and `Ctrl+left`/`Ctrl+right` seek by 1s for frame-level precision.
23. **IPC-not-ready fallback for progress bar** — synthesises a `PlayerStatus(is_playing=True)` from `MpvPlayer.is_playing()` + `get_live_progress()` (stdout data) when IPC is not yet available. Also renders an all-`░` placeholder bar during the startup transient.
24. **3-state sort cycle** — `on_data_table_header_selected` uses `_sort_state` int (0=unsorted, 1=ascending, 2=descending) instead of a boolean. Header labels show `↑`/`↓` when sorted.
25. **Smart refresh scoping** — `REFRESH_DAYS = 100` in `engine.py`. `fetch_feed_async()` accepts an optional `days_back` parameter. Auto-refresh passes `days_back=REFRESH_DAYS`; manual `u` refresh omits it (full archive).
26. **Schema versioning with migration pipeline** — `DataManager.STATE_VERSION = 1`. On `load()`, the stored `version` is checked; if lower, migrations from `_MIGRATIONS` dict are run sequentially.
27. **Unmark played** — `DataManager.unmark_played()` removes an episode from `_played` and `_played_order` and clears any saved progress.
28. **Mouse scrubbing** — `EpisodeScreen.on_click()` captures click coordinates relative to the status bar width during scrub mode, normalizes to a position ratio, and calls `MpvPlayer.seek_absolute()`.
29. **In-app help overlay** — `HelpScreen` is a modal `Screen` displaying a keybinding table for the current screen context. Activated by `?` on FeedScreen and EpisodeScreen. Dismissed with `Esc`, `Space`, `Enter`, `q`, or `?`.
30. **Theme system via CSS variables** — `src/theme.py` defines `DARK_THEME` and `LIGHT_THEME` dicts mapping CSS variable names to hex colors. `AetherPod.apply_theme()` calls `self.stylesheet.set_variables()` to switch between dark and light modes. The `t` key toggles `self.dark` and reapplies the appropriate variable map.
31. **LoadingSpinner as a Rich renderable** — `LoadingSpinner` in `src/widgets.py` is a custom renderable that cycles through braille characters (⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏) at 100ms intervals using `set_interval`. Replaces static "Refreshing..." text during async feed operations.
32. **Playback speed via mpv IPC** — `MpvPlayer.set_speed(factor)` sends `{"command": ["set_property", "speed", factor]}` over the Unix-socket IPC. Range is 0.5x–3.0x in 0.25x steps. Current speed is displayed in the status bar.
33. **NowPlayingScreen as a dedicated playback view** — Activated by `N` key. Shows a large progress bar, episode title, feed name, publication date, and transport controls (play/pause, stop, seek, speed). Pushes on top of the screen stack and pops back to EpisodeScreen on `Esc`.
34. **SearchScreen for cross-feed search** — Activated by `/` key. Presents a text input at the top and a DataTable of matching episode titles across all cached feeds. Results update in real time as the user types. Selecting a result navigates to the source feed's EpisodeScreen.
35. **EpisodeDetailScreen as a readable modal** — Activated by `d` key on a selected episode. Displays the full `summary`/description text in a scrollable `RichLog`, along with metadata (feed, date, duration, playback status). Dismissed with `Esc` or `q`.

## Logging Configuration

| Property | Value |
|---|---|
| **Log file** | `~/.local/state/aetherpod/log/aetherpod.log` |
| **Format** | `%(asctime)s  %(levelname)-8s  %(name)s  %(message)s` |
| **Timestamp** | ISO8601 via `datefmt="%Y-%m-%dT%H:%M:%S%z"` |
| **Default level** | `INFO` (stderr: WARNING+) |
| **Override** | `AETHERPOD_LOG_LEVEL` environment variable |

- Logging initialized in `src/cli.py` before any component is imported.
- Every module gets `logger = logging.getLogger(__name__)`.
- Log directory uses `platformdirs.user_state_dir("aetherpod")` — portable across distros.
- File handler at INFO level; stderr handler at WARNING level (no TUI noise).
