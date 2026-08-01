# Created: 2026-07-19
# Last Edited: 2026-08-01 03:48 CT (America/Chicago)
# Path: docs/sys/CHANGELOG.md
# Purpose: Release history for AetherPod.

# Changelog

## 2026-08-01 — v0.4.1 — Audit Remediation, Cross-Platform Builds, AetherSolDev Rebrand

### Added
- **Cross-platform executables** — `.github/workflows/build.yml` builds single-file PyInstaller binaries for Linux, macOS, and Windows (Python 3.12). Uploaded as artifacts on every push; attached to a GitHub Release on `v*` tag pushes.
- **EQ preset unit tests** — 11 tests for `_build_af_string` and `eq.json` load/fallback (suite now 37 tests).
- **Platform badges + tagline** — Linux/macOS/Windows shields and the *"BTW.. I use Arch"* tagline in README and splash screen.

### Changed
- **Rebrand to AetherSolDev** — repository moved to `github.com/AetherSolDev/AetherPod`; `--upgrade` URL, README clone URL, and `pyproject.toml` description updated; commits now authored by `AetherSol <support@aethersol.io>`.
- **Audit remediation (grade A)** — full linter-assisted re-audit; all F01–F28 findings resolved, including: scrubbed `data/state.json` from git history, narrowed `eq.json` load exception, removed 6 unused imports, sorted import blocks in 10 files, logged (not swallowed) widget-not-ready exceptions, regenerated audit reports fresh, updated maps + docs.

### Removed
- **Removed from git tracking** — `project_kit/`, `safety.md`, `uv.lock`, `Tayogo.json` (local-only files; the project does not use uv).

## 2026-08-01 — v0.4.0 — Audio EQ Presets

### Added
- **Audio EQ presets** — 3 voice-optimized profiles (Bright / Warm / Balanced) plus Off, applied via mpv `af` filter chain with highpass + parametric EQ + lookahead limiter. Toggle instantly with `1`–`4` on Episode and Now Playing screens. mpv only (VLC/ffplay are no-ops).
- **User-editable EQ config** — `eq.json` written to the config dir on first run; malformed values fall back to built-in defaults. (`aetherpod/eq_presets.py`)
- **EQ status indicators** — current preset shown in the Now Playing controls and Episode status bar when not "Off".

### Changed
- **`AudioEngine` ABC** — new abstract `set_eq(af_string)` method; MpvEngine applies it via IPC (with retry), VlcEngine/FfplayEngine no-op.
- **`Player`** — EQ preset state (`set_eq_preset`/`get_eq_preset`), re-applied to fresh mpv processes, and loaded at startup.
- **Help/README** — `1`–`4` EQ keys documented in HelpScreen, README, and docs/HELP.md.

## 2026-07-27 — v0.3.1 — Audit Re-run, New_Project_init removal, cache cleanup

### Added
- **Re-audit findings** — `docs/sys/AUDIT_REPORT.md` updated with automated tooling results (function inventory, dependency analysis, dynamic call audit)
- **Audit artifacts** — `docs/sys/dynamic_audit_report.txt`

### Changed
- **`.gitignore`** — `New_Project_init/` added to gitignore
- **`New_Project_init/`** — untracked from git (was a template/setup scaffold, not part of the app)

### Removed
- **Cache directories** — all `__pycache__/` and `.pytest_cache/` cleaned from local tree

## 2026-07-27 — v0.3.0 — Codebase Audit & Structural Overhaul

### Changed
- **Package renamed `src/` → `aetherpod/`** — all imports updated from `from src.xxx` to `from aetherpod.xxx`. `pyproject.toml` and `Makefile` updated. Prevents namespace collisions with sibling projects.
- **`screens.py` split into `aetherpod/screens/` package** — 1932-line monolithic file broken into 10 focused files: `feed_screen.py`, `episode_screen.py`, `dialogs.py`, `now_playing.py`, `search.py`, `detail_help.py`, `splash.py`, `queue.py`, `helpers.py`, `__init__.py`.
- **`engine.py` split** — RSS fetching functions extracted to `aetherpod/rss.py`; shared dataclasses (`Episode`, `ProgressInfo`, `FeedResult`) extracted to `aetherpod/models.py`.
- **`AGENTS.md`** — stale `/home/systemd/projects/podb/` paths updated to `AetherPod/`. Documentation references updated.
- **`theme.py`** — `PODB_DARK`/`PODB_LIGHT` renamed to `AETHERPOD_DARK`/`AETHERPOD_LIGHT`.
- **`app.py`** — `__import__('src')` hack replaced with explicit `from aetherpod import __version__`.
- **CI/CD** — `.github/workflows/ci.yml` added (tests on push/PR for Python 3.10–3.13).

### Added
- **`maps/` directory** — `architecture.md` (directory tree + component responsibilities) and `imports.mmd` (Mermaid dependency graph).
- **Test suite** — `tests/unit/test_engine.py` (14 tests for `DataManager`) and `tests/unit/test_rss.py` (12 tests for RSS helpers). All 26 tests pass.
- **`docs/sys/KNOWLEDGE.md`** populated with Architecture TL;DR, Critical Files Map, Key Decisions, Gotchas, Code Patterns, Navigation Hints, Session History.
- **`docs/sys/AUDIT_REPORT.md`** — full codebase audit report with findings, scoring, and remediation progress.

### Fixed
- **`_parse_feed_date(None)` crash** — added None guard. Caught by new test suite.
- **Line length violations** — 20 lines exceeding 100 chars across 6 files shortened to PEP 8 compliance.
- **File header timestamps** — refreshed across all edited files.

## 2026-07-26 — v0.2.1 — Audio Engine Abstraction & GitHub Upgrade

### Added
- **AudioEngine abstraction** — `src/engines.py` with `AudioEngine` ABC and three concrete engines
- **Version bumped to 0.2.1**
- **`--upgrade` now pulls from GitHub** by default (`git+https://github.com/brandonmunoz1975-ops/AetherPod.git`) instead of PyPI
- **Editable-mode `--upgrade` auto-runs `git pull`** — detects editable install, runs `git pull` in the project directory, then reinstalls with `pip install -e .`
- **`--upgrade` handles `--break-system-packages`** — auto-adds the flag when running outside a venv (Python 3.11+), fixing the macOS/Linux system-python case. Pip errors are now displayed to the user.: `MpvEngine` (Unix-socket IPC), `VlcEngine` (RC-over-TCP), `FfplayEngine` (minimal stdin). Auto-detected in priority order: mpv > VLC > ffplay.
- **VlcEngine** — `--intf rc` over `AF_INET` socket (works on Linux, macOS, and Windows). Supports play, stop, pause, seek, speed, and progress querying.
- **FfplayEngine** — minimal fallback using stdin for pause toggle. No seek or speed control, but ensures playback works when mpv and VLC are both absent.
- **detect_engine() factory** — checks PATH for each binary and returns the best available engine, or `None` if none found.

### Changed
- **MpvPlayer → Player** — `src/player.py` refactored from a monolithic mpv wrapper to an engine-agnostic `Player` class that delegates media operations to its `AudioEngine`. Queue, cache, and progress callback logic stay in `Player`.
- **PlayerStatus moved to src/engines.py** — shared by all engines and the Player class.
- **All screen type annotations updated** — `MpvPlayer` → `Player` in `FeedScreen`, `EpisodeScreen`, `NowPlayingScreen`, `QueueScreen`, `SearchScreen`, `EpisodeDetailScreen`, `SplashScreen`.

### Windows / macOS Compatibility
- **macOS**: Fully supported — `AF_UNIX` sockets work natively, mpv via Homebrew.
- **Windows**: Supported via `VlcEngine` (VLC's RC interface uses TCP, not Unix sockets). MpvEngine remains Linux/macOS-only due to `AF_UNIX`. FfplayEngine provides a minimal fallback.

## 2026-07-25 — v0.2.0 Release Candidate — Splash, Queue, Polish

### Added
- **Branded splash screen** — ASCII logo + app stats + feature list with Catppuccin-like theme. Auto-dismisses on keypress or timer. (src/splash.py, src/screens.py)
- **Play queue** — `a` adds to queue, `v` opens queue screen, auto-plays next on natural end. Queue count shown in status bar. (src/player.py, src/screens.py)
- **Global pause** — `Space` works from any screen (Feed, Episode, Queue, etc.). (src/app.py)
- **Now-playing indicator on FeedScreen** — `▶` prefix next to the feed containing the currently-playing episode. (src/screens.py)
- **Configurable refresh window** — `refresh_days` in `state.json` (default 100). (src/engine.py)
- **Auto-download for resume** — episodes with saved progress are downloaded to `~/.cache/aetherpod/` before playing, ensuring `--start` works reliably on any CDN. (src/player.py, src/screens.py)
- **CLI `--upgrade` flag** — runs `pip install --upgrade aetherpod`. (src/cli.py)
- **Portable paths** — log and state use `platformdirs` (`~/.local/state/aetherpod/`) instead of script-relative paths. (src/cli.py, src/engine.py)
- **Stderr noise reduction** — only WARNING+ messages go to stderr; INFO stays in log file. (src/cli.py)
- **GPLv3 license** — LICENSE file added.
- **Version bump script** — `scripts/bump_version.sh` (gitignored, local only).

### Fixed
- **Progress bar not updating on EpisodeScreen** — added 30s periodic full `_populate()` and `table.refresh()` after every `update_cell()`.
- **Resume crash with CDNs rejecting `--start`** — mpv exiting with code 1 is detected after 300ms; auto-retry without resume position.
- **Double-Enter race** — `_do_play` skips stop+replay if same episode already playing.
- **Header title** — now consistently shows `AetherPod - v0.2.0` on all screens.
- **Help screen** — updated with queue, global pause, and all missing keybindings.

### Changed
- **Renamed `main.py` → `aetherpod.py`** — cleaner GitHub presence.
- **pyproject.toml** — console_scripts entry point for `aetherpod` command.
- **All `self.title` overrides removed** — header shows app title uniformly.

## 2026-07-24 — Rename to AetherPod, v0.2.0, New Screens & Features

### Added
- **Rename from podb to AetherPod** — project renamed to AetherPod, version bumped to 0.2.0.
- **Playback speed control** — `[` and `]` keys adjust mpv playback speed (0.5x–3.0x), displayed in status bar. (src/player.py, src/screens.py)
- **Episode detail popup** — `d` key opens a modal `EpisodeDetailScreen` showing full episode description, publication date, and duration. (src/screens.py)
- **Search across feeds** — `/` key opens `SearchScreen` with a search input; results shown in a DataTable across all cached episodes. (src/screens.py)
- **Now-playing screen** — `N` key opens `NowPlayingScreen` with full-screen playback view showing large progress bar, metadata, and controls. (src/screens.py)
- **Custom dark/light theme system** — palette ported from PySide6 theme.py to Textual CSS variables. Dark: navy base (#1a1a2e) with blue (#54a0ff) and teal (#00d2d3) accents. Toggle with `t` key. (src/theme.py, src/app.py)
- **Animated loading spinner** — braille spinner (⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏) cycles during feed refresh instead of static "Refreshing..." text. (src/widgets.py)
- **Playing row highlight** — active episode row gets a dark teal background (#003333) so you can always see what's playing. (src/screens.py)
- **Segmented status bar** — color-coded pipe-separated sections for episode stats, playback position, and action hints. (src/screens.py)
- **Dynamic progress bar width** — progress bars now show percentage text and use proportional width (30 chars). (src/screens.py)
- **HelpScreen Rich formatting** — keybindings styled with cyan keys, category headers, and dim descriptions instead of raw string tables. (src/screens.py)
- **Dialog input validation** — AddFeedDialog validates URL format and shows inline error messages in red. (src/screens.py)

### Fixed
- **`_format_date` cross-screen reference** — `_format_date()` was a method on `EpisodeScreen` but called from `EpisodeDetailScreen` and `SearchScreen`, causing `AttributeError`. Moved to a module-level helper function. (src/screens.py)
- **`_poll_playback` stack ordering** — polling walked the full screen stack and could update stale `EpisodeScreen` instances. Now only updates the topmost `EpisodeScreen`. (src/app.py)
- **`_refresh_playing_item` fallback for ID-less episodes** — episodes without an `episode_id` caused `_refresh_playing_item()` to crash. Added guard for missing ID. (src/screens.py)
- **`_wait_loop` bare `except: pass`** — replaced with logged warnings so stdout read errors are visible in logs. (src/player.py)
- **`_close_ipc` exception** — `except Exception: pass` replaced with logged debug message. (src/player.py)
- **Generation check race** — `_generation` now read under `_lock` before cleanup decision in `_wait_loop`. (src/player.py)

## 2026-07-24 — Visual Polish & Theme System

### Added
- **Custom dark/light theme system** — palette ported from PySide6 theme.py to Textual CSS variables. Dark: navy base (#1a1a2e) with blue (#54a0ff) and teal (#00d2d3) accents. Toggle with `t` key. (src/theme.py, src/app.py)
- **Animated loading spinner** — braille spinner (⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏) cycles during feed refresh instead of static "Refreshing..." text. (src/widgets.py)
- **Playing row highlight** — active episode row gets a dark teal background (#003333) so you can always see what's playing. (src/screens.py)
- **Segmented status bar** — color-coded pipe-separated sections for episode stats, playback position, and action hints. (src/screens.py)
- **Dynamic progress bar width** — progress bars now show percentage text and use proportional width (30 chars). (src/screens.py)
- **HelpScreen Rich formatting** — keybindings styled with cyan keys, category headers, and dim descriptions instead of raw string tables. (src/screens.py)
- **Dialog input validation** — AddFeedDialog validates URL format and shows inline error messages in red. (src/screens.py)

### Fixed
- **`_wait_loop` bare `except: pass`** — replaced with logged warnings so stdout read errors are visible in logs. (src/player.py)
- **Generation check race** — `_generation` now read under `_lock` before cleanup decision in `_wait_loop`. (src/player.py)
- **`_close_ipc` exception** — `except Exception: pass` replaced with logged debug message. (src/player.py)

## 2026-07-20

### Added (Phase 9)

- **Mark played/unplayed** (`m` key on EpisodeScreen) — toggle an episode's played status instantly. `DataManager.unmark_played()` clears the played flag and any saved progress. (src/engine.py, src/screens.py)
- **Restart from beginning** (`r` key during playback) — stops mpv, clears saved progress, and replays from position 0. (src/screens.py)
- **Sort 3-state cycle** — clicking a column header now cycles: unsorted → ascending (↑) → descending (↓) → unsorted. Arrow direction matches data order. (src/screens.py)
- **Smart refresh scoping** — auto-refresh (startup, feed add/remove) only fetches episodes from the last 100 days; full refresh (`u` key) fetches all. `REFRESH_DAYS = 100` constant in engine.py. (src/engine.py, src/screens.py)
- **Schema versioning** — `STATE_VERSION = 1` with automatic migration pipeline (`_MIGRATIONS` registry). Old `state.json` files without a `version` key are auto-migrated on next load. `--version` CLI flag shows `AetherPod 0.1.0`. (src/engine.py, src/__init__.py, main.py)
- **Mouse scrubbing** — during scrub mode, click on the timeline bar in the status bar to seek to any position. (src/screens.py)
- **In-app help** (`?` key) — modal `HelpScreen` shows all keybindings for the current screen. (src/screens.py, src/app.py)
- **INSTALL.md** — installation guide for Arch Linux (and general Linux/macOS/Windows).
- **HELP.md** — user-facing keybinding reference and CLI guide.

### Fixed (Phase 9)

- **`DataTable.get_row_keys()` → `table.row_keys`** — `action_play()` and `action_toggle_played()` used a non‑existent `get_row_keys()` method which raised `AttributeError` when pressing Enter or `m`. Changed to the correct `table.row_keys` property. (src/screens.py)
- **MouseDown crash on Label click** — `ALLOW_SELECT = False` is set but Textual 8.2.8 enters the selection code path anyway when a `Label` widget has `.parent == None` (e.g. during `ListView` virtual scrolling). Added an `App._forward_event()` override that catches the `AttributeError: 'NoneType' object has no attribute 'region'` and logs it at DEBUG instead of crashing. (src/app.py)
- **Progress bar not updating during playback** — the progress bar and timeline bar used `MpvPlayer.get_live_progress()` (stdout parsing) which could return `(0.0, 0.0)` during IPC startup transient. Changed `_refresh_playing_item()`, `_build_row_cells()`, and `_update_status_bar()` to prefer `self._player_status` (IPC data) and only fall back to stdout live progress when IPC data is unavailable. Also removed an unnecessary `row_key.value is None` guard that could silently prevent updates. (src/screens.py)
- **Diagnostic logging for stdout parsing** — `_wait_loop()` now logs the first `POS=… LEN=…` match and any raw unmatched lines, making it easier to debug if `--term-status-msg` output is not being parsed correctly. (src/player.py)

- **Enter key not starting player on EpisodeScreen** — `DataTable` in Textual 8.2.8 has a built-in `enter` → `select_cursor` binding that consumed the key before `EpisodeScreen.action_play()` could fire. Added `priority=True` to the screen-level binding so it takes precedence over the widget binding. (src/screens.py)
- **`?` help key shrinking Title column** — `action_show_help()` had orphaned column-width adjustment code after the `push_screen()` call that ran every time help was opened, shrinking the Title column by 4 characters. Removed the leaked lines. (src/screens.py)

### Changed

- **`fetch_feed_async()`** now accepts optional `days_back` parameter for smart refresh scoping. (src/engine.py)
- **`DataManager.save()`** always writes `"version": STATE_VERSION`. (src/engine.py)
- **`DataManager.load()`** runs schema migrations automatically when stored version < `STATE_VERSION`. (src/engine.py)
- **EpisodeScreen docstring** updated to document `m` (mark), `r` (restart), and `?` (help) actions.
- **FeedScreen docstring** updated to document `?` (help) action.

### Fixed

- **P0 bug marked done in BUGS.md** — live progress bar was already fixed in Phase 8 via byte-level stdout reading with `\r`/`\n` splitting. BUGS.md tracking updated to ✅ Fixed.
