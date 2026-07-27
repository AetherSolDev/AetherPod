# Created: 2026-07-27
# Last Edited: 2026-07-27 15:54 CT (America/Chicago)
# Path: maps/architecture.md
# Purpose: High-level directory structure and component responsibilities for AetherPod.

# Architecture Map

## Directory Tree

```
AetherPod/
├── aetherpod.py                  # Thin entry point — delegates to aetherpod.cli:main
├── aetherpod/                    # Application package
│   ├── __init__.py               # Package marker — exports __version__
│   ├── cli.py                    # CLI entry point — argparse, logging, headless commands
│   ├── app.py                    # Root Textual App — screen orchestration, CSS, polling
│   ├── engine.py                 # DataManager — JSON state persistence (feeds, played, progress)
│   ├── models.py                 # Shared dataclasses — Episode, ProgressInfo, FeedResult
│   ├── rss.py                    # RSS/Atom feed fetching — fetch_feed, fetch_feed_async, helpers
│   ├── engines.py                # AudioEngine ABC + MpvEngine/VlcEngine/FfplayEngine + factory
│   ├── player.py                 # Player — queue, cache, progress callbacks, engine wrapper
│   ├── widgets.py                # LoadingSpinner reusable widget
│   ├── splash.py                 # SplashRenderable — Rich startup screen
│   ├── theme.py                  # Custom Textual dark/light themes
│   └── screens/                  # Textual screens (split from monolithic screens.py)
│       ├── __init__.py           # Re-exports all screen classes
│       ├── helpers.py            # format_date() shared utility
│       ├── feed_screen.py        # FeedScreen — feed subscription list
│       ├── episode_screen.py     # EpisodeScreen — episode browser, play, sort, search
│       ├── dialogs.py            # AddFeedDialog, PathInputDialog
│       ├── now_playing.py        # NowPlayingScreen — full-screen playback view
│       ├── search.py             # SearchScreen — cross-feed search
│       ├── detail_help.py        # EpisodeDetailScreen, HelpScreen
│       ├── splash.py             # SplashScreen — startup splash (textual screen)
│       └── queue.py              # QueueScreen — play queue management
├── maps/                         # Architecture maps
│   ├── architecture.md           # This file
│   └── imports.mmd               # Mermaid dependency graph
├── tests/                        # Test suite
│   ├── __init__.py
│   └── unit/
│       ├── __init__.py
│       ├── test_engine.py        # 14 tests for DataManager
│       └── test_rss.py           # 12 tests for RSS helpers
├── docs/sys/                     # System docs (plan, tasks, changelog, audit, etc.)
├── scripts/                      # Build/dev utility scripts
├── venv/                         # Virtual environment
├── AGENTS.md                     # Master agent rules
├── pyproject.toml                # Package metadata
├── Makefile                      # Install/uninstall targets
├── requirements.txt              # Dependencies
└── ...
```

## Key Relationships

- `cli.py` imports `engine.py` (DataManager) and `rss.py` (fetch_feed) and lazy-imports `app.py`
- `app.py` imports `engine.py`, `player.py`, `models.py`, individual screen modules, `theme.py`
- `screens/` modules import `engine.py`, `models.py`, `rss.py`, `engines.py`, `player.py`, `widgets.py`
- `player.py` imports `engines.py`
- No circular imports — dependency graph is a DAG (one lazy import in queue.py)

## Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| DataManager | JSON state persistence (feeds, played, progress, cache, headers) |
| RSS (rss.py) | RSS/Atom parsing via feedparser, conditional GET, date parsing |
| AudioEngine (ABC) | Subprocess audio backend interface |
| Player | Media orchestration — queue, cache, progress, engine delegation |
| Screens | Textual UI — 10 screen classes across 9 files |
| CLI | Argument parsing, headless commands, upgrade logic, logging setup |
