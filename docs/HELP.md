# Created: 2026-07-20
# Last Edited: 2026-08-01 12:29 CT (America/Chicago)
# Path: docs/HELP.md
# Purpose: User guide and keybinding reference for AetherPod.

# AetherPod — Help & Reference

## Keybindings

### Feed Screen (feed list)

| Key       | Action            |
|-----------|-------------------|
| `a`       | Add a feed URL    |
| `i`       | Import OPML file  |
| `e`       | Export OPML file  |
| `u`       | Refresh all feeds |
| `r`       | Remove feed       |
| `s`       | Sort feeds: subscribe order → A→Z → Z→A |
| `f`       | Filter feeds by name (type to filter, `Esc`/`f` to clear) |
| `Enter`   | Browse episodes   |
| `/`       | Search episodes across all feeds |
| `Space`   | Toggle pause/resume (global) |
| `t`       | Toggle theme      |
| `q`       | Quit AetherPod    |
| `?`       | Show this help    |

### Episode Screen (episode list)

| Key              | Action                     |
|------------------|----------------------------|
| `Esc`            | Go back to feed list       |
| `Enter`          | Play selected episode      |
| `Space`          | Toggle pause/resume (global)|
| `s`              | Stop playback              |
| `d`              | Show episode details       |
| `N`              | Now-playing full-screen    |
| `m`              | Mark played/unplayed       |
| `r`              | Restart from beginning     |
| `u`              | Full refresh (no date limit)|
| `f`              | Toggle unplayed-only filter|
| `←` / `→`        | Seek -30s / +30s          |
| `Ctrl+← / Ctrl+→`| Seek -1s / +1s            |
| `[` / `]`        | Speed down / up (0.5x–3.0x)|
| `1` / `2` / `3` / `4` | EQ presets: Off / Bright / Warm / Balanced |
| `.`              | Toggle scrub mode          |
| `a`              | Add to play queue          |
| `A`              | Play next (stop current)   |
| `v`              | View play queue            |
| `t`              | Toggle theme               |
| `q`              | Quit AetherPod             |
| `?`              | Show this help             |

### Scrub Mode (active when `.` pressed during playback)

| Key              | Action                     |
|------------------|----------------------------|
| `←` / `→`        | Seek by 5 seconds          |
| `Ctrl+← / Ctrl+→`| Seek by 1 second           |
| `Esc`            | Exit scrub mode            |
| **Mouse click**  | Click timeline bar to seek |

### Play Queue (press `v` on Episode Screen)

| Key       | Action            |
|-----------|-------------------|
| `Enter`   | Play selected + remove from queue |
| `d`       | Remove from queue |
| `c`       | Clear queue       |
| `Esc`     | Close queue view  |

## Theme

Press `t` at any screen to toggle between the dark theme (navy base, blue/teal accents)
and the light theme (white background, dark text).

Feed and episode lists use zebra striping (alternating row shades) to make
scanning easier. Rows with a `▷` prefix are currently playing.

## Updating

On startup, AetherPod checks GitHub for a newer release. If one exists, a
notification appears (e.g. *"Update available: v0.4.3 (you have v0.4.2). Quit
and run 'aetherpod -u' to upgrade."*). The check is silent if offline.

- `aetherpod -u` upgrades editable / pip installs straight from git.
- Executable (bundled binary) installs must download the new binary from the
  [Releases](https://github.com/AetherSolDev/AetherPod/releases) page — `-u`
  requires pip/git and does not work inside a bundled executable.

## Filtering Feeds

- **Sort** (`s`) — cycles through *subscribe order → A→Z → Z→A* by feed title.
- **Filter** (`f`) — opens an inline input; feeds are filtered by name as you type.
  Press `Esc` (or `f` again) to close and clear the filter.

## CLI Commands

```bash
aetherpod [command]
```

| Command   | Description                            |
|-----------|----------------------------------------|
| `tui`     | Launch the TUI (default)               |
| `list`    | List subscribed feeds and episode counts|
| `add <url>` | Subscribe to a new feed URL           |
| `refresh` | Fetch all feeds and show episode titles|
| `import <path>` | Import feeds from OPML file       |
| `export <path>` | Export feeds to OPML file          |
| `reset`   | Clear all state                        |
| `--version` | Show version and exit                |
| `--upgrade` | Upgrade to latest version            |
| `--data <path>` | Use custom state file path         |
| `--help`  | Show CLI usage                        |

## State File

AetherPod stores its state in `~/.local/state/aetherpod/state.json`. This file contains:

- **feeds**: List of subscribed RSS/Atom feed URLs
- **played_episodes**: History of played episodes (up to 50; oldest are trimmed)
- **episode_progress**: Resume positions for partially-listened episodes
- **feed_headers**: ETag/Last-Modified headers for conditional HTTP fetches
- **feed_cache**: Cached feed metadata for instant startup
- **refresh_days**: Configurable refresh window (default 100)
- **version**: Schema version number (for automatic migration)

Override state path with `--data /custom/path.json` (supports relative paths for USB portability).

## OPML Import / Export

- **Import**: `aetherpod import /path/to/subscriptions.opml`
- **Export**: `aetherpod export /path/to/output.opml`
- In-app: Press `i` (import) or `e` (export) on the Feed Screen

OPML 1.0 and 2.0 formats are supported for import; export always produces OPML 2.0.

## Smart Refresh

- **Auto-refresh** (startup, feed add/remove): Only fetches episodes from the last N days (configurable via `state.json` → `refresh_days`, default 100).
- **Full refresh** (`u` key on Episode Screen): Fetches all episodes from the feed, with no date limit.

## Playback

AetherPod auto-detects the best available audio engine:

**Engine detection by platform:**
- **Linux / macOS**: mpv (preferred) → VLC → ffplay
- **Windows**: VLC (preferred — mpv's control channel is Unix-socket only and
  unsupported on Windows) → ffplay

**Detection beyond PATH:** AetherPod finds engines even when they aren't on PATH:
- **Windows** — standard `Program Files` install locations and the registry
  (`SOFTWARE\VideoLAN\VLC` → `InstallDir`)
- **macOS** — VLC.app bundle (`/Applications/VLC.app/Contents/MacOS/vlc`) and
  Homebrew (`/opt/homebrew` on Apple Silicon, `/usr/local` on Intel)

If you still see *"No audio engine found"*, ensure the player is installed
or add its folder to PATH.

### mpv (Linux/macOS)

Controls flow through a Unix-socket IPC
channel for low-latency communication:

- Real-time progress bar updates via mpv's `--term-status-msg` output
- Resume support: partially-listened episodes start from where you left off
- Auto-download for resume: if an episode has saved progress, it is downloaded to `~/.cache/aetherpod/` before playing so `--start` works reliably on any CDN
- Scrubbing: fine-grained seeking with visual timeline bar
- Mouse scrubbing: click on the timeline bar to jump to any position
- Speed control: `[` and `]` adjust playback speed from 0.5x to 3.0x in 0.25x steps
- Play queue: add episodes with `a`, auto-plays next on natural end

## Audio EQ

AetherPod includes 3 voice-optimized EQ presets (plus Off) that apply a
lavfi parametric equalizer chain + lookahead limiter through mpv's `af`
property at runtime:

| Key | Preset | Character |
|-----|--------|-----------|
| `1` | **Off** | Unmodified audio |
| `2` | **Bright** | Voice clarity — boosted presence (2.5–5 kHz), gentle low-end cut, thin/crisp |
| `3` | **Warm** | Full-bodied — boosted lows (100–500 Hz), rolled-off highs, boomy/dark |
| `4` | **Balanced** | Middle ground — slight warmth + presence, moderate shaping |

Each preset includes a lookahead limiter with input gain boost (±5 dB) to give
a compressed *loudness* feel while preventing peaks from clipping.

**mpv only** — EQ requires mpv's lavfi bridge and is silently ignored when
using VLC or ffplay as the audio engine.

**Windows users:** because AetherPod uses VLC on Windows (mpv's control
channel is Linux/macOS-only), the EQ presets are **not available on Windows**.
The `1`–`4` keys still work but have no effect. mpv-on-Windows support (which
would enable EQ) is on the roadmap.

### Customizing presets

Presets are stored as plain JSON at **`~/.config/aetherpod/eq.json`** (created
automatically on first launch). The in-app help lists the current preset name
in the status bar (e.g. `EQ:Bright`).

The file is structured as:

```json
{
  "_readme": "highpass: {frequency} or null.  eq: [{frequency, gain, q}...].  limiter: {level_in, limit, attack, release} or null.",
  "presets": [
    {
      "label": "Off",
      "highpass": null,
      "eq": [],
      "limiter": null
    },
    {
      "label": "Bright",
      "highpass": {"frequency": 100},
      "eq": [
        {"frequency": 200, "gain": -2, "q": 1},
        {"frequency": 300, "gain": 2, "q": 1},
        ...
      ],
      "limiter": {"level_in": 1.8, "limit": 0.89, "attack": 3, "release": 30}
    }
  ]
}
```

Edit the values freely — invalid JSON falls back to the built-in defaults.
The lavfi filter string is rebuilt from the JSON at load time.

## Logs

Logs are written to `~/.local/state/aetherpod/log/aetherpod.log`. Only WARNING+
messages appear on stderr; INFO goes to the log file only.

## Verify

This is AetherPod **v0.4.3**. Run `aetherpod --version` to confirm.
