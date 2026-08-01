# Created: 2026-07-19
# Last Edited: 2026-08-01 11:41 CT (America/Chicago)
# Path: docs/sys/ARCHITECTURE.md
# Purpose: High-level component map and design rationale for AetherPod.

# AetherPod Architecture

```
AetherPod/
├── aetherpod.py                  # CLI entry point (thin wrapper → aetherpod.cli:main)
├── pyproject.toml                # Package metadata + console_scripts
├── requirements.txt              # aiohttp, feedparser, textual
├── Makefile                      # Install/uninstall targets
├── README.md
├── LICENSE                       # GPLv3
├── .github/workflows/
│   └── ci.yml                    # CI: test on push/PR (Python 3.10–3.13)
├── maps/
│   ├── architecture.md           # Directory tree + component responsibilities
│   └── imports.mmd               # Mermaid dependency graph
├── aetherpod/                    # Application package
│   ├── __init__.py               # Version
│   ├── app.py                    # AetherPod App — CSS, screens, 1s poll
│   ├── cli.py                    # CLI logic (argparse, upgrade, logging)
│   ├── engine.py                 # DataManager — JSON state persistence
│   ├── models.py                 # Shared dataclasses — Episode, ProgressInfo, FeedResult
│   ├── rss.py                    # RSS/Atom feed fetching (sync + async)
│   ├── engines.py                # AudioEngine ABC + MpvEngine/VlcEngine/FfplayEngine
│   ├── player.py                 # Player (engine-agnostic) + queue + auto-download cache
│   ├── splash.py                 # SplashRenderable
│   ├── theme.py                  # Dark/light Theme definitions
│   ├── widgets.py                # LoadingSpinner
│   └── screens/                  # Textual screens (10 files)
│       ├── __init__.py           # Re-exports all screens
│       ├── helpers.py            # format_date() shared utility
│       ├── feed_screen.py        # FeedScreen
│       ├── episode_screen.py     # EpisodeScreen
│       ├── dialogs.py            # AddFeedDialog, PathInputDialog
│       ├── now_playing.py        # NowPlayingScreen
│       ├── search.py             # SearchScreen
│       ├── detail_help.py        # EpisodeDetailScreen, HelpScreen
│       ├── splash.py             # SplashScreen
│       └── queue.py              # QueueScreen
├── tests/
│   ├── __init__.py
│   └── unit/
│       ├── __init__.py
│       ├── test_engine.py        # 14 DataManager tests
│       └── test_rss.py           # 12 RSS helper tests
├── data/
│   └── state.json                # Runtime state (~/.local/state/aetherpod/state.json)
├── docs/
│   ├── sys/                      # System docs (plan, tasks, changelog, audit, etc.)
│   └── USER_GUIDE.md             # User-facing documentation
└── scripts/                      # Build/dev utility scripts
```

## Architecture Principles

1. **Separation of concerns** — UI (screens/) ↔ State (engine.py) ↔ Audio (player.py + engines.py) ↔ Data (rss.py + models.py)
2. **No circular imports** — dependency graph is a DAG. One lazy import in queue.py breaks the only potential cycle.
3. **Testability** — core logic (DataManager, RSS parsing) tested with 26 unit tests. State is JSON on disk, easy to mock.

## Data Flow

```
User Input → Screen → Player/DataManager → AudioEngine (mpv/VLC/ffplay)
                ↓
           RSS fetch (feedparser + aiohttp/urllib) → DataManager cache
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Textual (TUI) | Python-native, async-first, hot-reload CSS, rich widget set |
| `aetherpod/` package | Namespaced to avoid collisions with sibling projects |
| JSON state (not SQLite) | Simple schema, no migration complexity for single-user app |
| mpv > VLC > ffplay auto-detect | Best-effort audio — mpv preferred, ffplay as last resort |
| List zebra striping | Feed list via `ListItem.zebra` class (Textual has no `:nth-child`); DataTables via native `zebra_stripes` |
| Feed sort/filter | `s` cycles subscribe→A-Z→Z-A by cached title; `f` inline name filter (`_display_order()` shared by both render paths) |
