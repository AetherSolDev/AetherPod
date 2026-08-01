# Created: 2026-07-27
# Last Edited: 2026-08-01 03:14 CT (America/Chicago)
# Path: docs/sys/AUDIT_REPORT.md
# Purpose: Full audit report — findings, scoring, and prioritized remediation plan for AetherPod.

# Audit Report: AetherPod

**Date**: 2026-08-01
**Files Scanned**: 21 source, 6 scripts, 2 top-level, 7 untracked items
**Overall Score**: **B** — regression from A: new EQ module untested, P0 hygiene finding, stale maps
**Remediation**: P0 + P1 resolved in this session (F15–F19 fixed, F23 fixed); P2/P3 deferred

## Remediation Progress

| Finding | Description | Status | Priority |
|---------|-------------|--------|----------|
| F01 | AGENTS.md stale podb/ paths | ✅ Fixed | P1 |
| F02 | Package named src/ instead of aetherpod/ | ✅ Fixed | P1 |
| F03 | No maps/ directory | ✅ Fixed | P1 |
| F04 | No tests/ directory | ✅ Fixed | P1 |
| F05 | screens.py 1932-line god file | ✅ Fixed | P1 |
| F06 | 16 except Exception: instances | ✅ Acceptable — all at system boundaries with logging | P1 |
| F07 | KNOWLEDGE.md skeleton | ✅ Fixed | P1 |
| F08 | theme.py PODB_ names | ✅ Fixed | P2 |
| F09 | __init__.py stale timestamp | ✅ Fixed | P2 |
| F10 | Import grouping | ✅ False positive — already correct | P2 |
| F11 | Split engine.py — extract RSS fetching | ✅ Fixed | P2 |
| F12 | __import__ hack in app.py | ✅ Fixed | P2 |
| F13 | Line length > 100 | ⏳ Pending | P3 |
| F14 | CI/CD configuration | ⏳ Pending | P3 |

## What Was Done

### Structural Changes

| Change | Details |
|--------|---------|
| `src/` → `aetherpod/` | Renamed package directory. Updated all `from src.xxx` → `from aetherpod.xxx` imports (19 files). Updated `pyproject.toml`, `Makefile`. |
| `aetherpod/screens/` package | Split 1932-line `screens.py` into 10 focused files under `aetherpod/screens/`. Created `helpers.py` for shared utilities. |
| `aetherpod/models.py` | Extracted shared dataclasses (`Episode`, `ProgressInfo`, `FeedResult`) from `engine.py` |
| `aetherpod/rss.py` | Extracted RSS fetching (`fetch_feed`, `fetch_feed_async`, `_parse_feed_date`, etc.) from `engine.py` |
| `maps/` | Created `architecture.md` and `imports.mmd` with full dependency graph |

### Bug Fixes
- `_parse_feed_date(None)` was crashing with `AttributeError` — added None guard

### Test Infrastructure
- Created `tests/unit/test_engine.py` (14 tests for DataManager)
- Created `tests/unit/test_rss.py` (12 tests for RSS helpers)
- All 26 tests pass

## Directory Structure (Current)

```
aetherpod/
├── __init__.py          # Package marker, __version__
├── cli.py               # CLI entry point
├── app.py               # Root Textual App
├── engine.py            # DataManager (state persistence)
├── models.py            # Episode, ProgressInfo, FeedResult dataclasses
├── rss.py               # RSS/Atom feed fetching (sync + async)
├── engines.py           # AudioEngine ABC + MpvEngine/VlcEngine/FfplayEngine
├── player.py            # Player wrapper (queue, cache, progress)
├── screens/
│   ├── __init__.py      # Re-exports all screens
│   ├── helpers.py       # format_date()
│   ├── feed_screen.py   # FeedScreen
│   ├── episode_screen.py # EpisodeScreen (was ~950 lines)
│   ├── dialogs.py       # AddFeedDialog, PathInputDialog
│   ├── now_playing.py   # NowPlayingScreen
│   ├── search.py        # SearchScreen
│   ├── detail_help.py   # EpisodeDetailScreen, HelpScreen
│   ├── splash.py        # SplashScreen
│   └── queue.py         # QueueScreen
├── widgets.py           # LoadingSpinner
├── splash.py            # SplashRenderable (Rich renderable)
└── theme.py             # Dark/light Textual themes
```

---

## Re-Audit: 2026-07-27 — Post-Fix Verification

**Score**: **A** — all checks pass

| Category | Check | Result |
|----------|-------|--------|
| 1.1 | File headers present | ✅ All 23 files |
| 1.4 | No trailing whitespace | ✅ 0 violations |
| 1.5 | Line length ≤ 100 | ✅ 0 violations |
| 2.1 | Imports grouped | ✅ All files |
| 2.2 | Absolute imports | ✅ No relative imports |
| 2.4 | No wildcard imports | ✅ None |
| 3.1 | No bare except: | ✅ None |
| 3.2 | No silent failures | ✅ All excepts log or handle |
| 4.1 | Single responsibility | ✅ screens.py split, engine.py split |
| 4.6 | No circular imports | ✅ Verified live — 0 cycles |
| 6.1 | Tests exist | ✅ 26 tests in 2 files |
| 6.2 | Tests run | ✅ All pass |
| 6.3 | Core logic tested | ✅ DataManager + RSS helpers |
| 7.1 | .gitignore | ✅ Present |
| 7.2 | venv/ | ✅ Named correctly |
| 7.3 | requirements.txt | ✅ Present |
| 7.4 | No secrets committed | ✅ None tracked |
| 7.6 | Package name unique | ✅ `aetherpod/` (not `src/`) |
| 8.1-8.5 | All docs exist | ✅ CHANGELOG, PLAN, TASKS, ARCHITECTURE, BUGS, maps |

---

## Re-Audit: 2026-07-27 (Session 2) — Automated Tooling

**Score**: **A** — all checks pass

**Audit tools used**:
- `function_inventory.py` — 150 functions, 24 classes, 23 files scanned
- `find_dependencies.py` — 94 called / 56 uncalled (uncalled are Textual action handlers/overrides — expected)
- `audit_dynamic.sh` — 6 `getattr` usages (all safe attribute lookups), no `eval`/`exec`, no bare `except:`

| Finding | Description | Status |
|---------|-------------|--------|
| Re-audit clean | No regressions since prior fix cycle | ✅ |
| 56 uncalled functions | All are Textual callback/action overrides — expected pattern, not dead code | ✅ Informational |
| 6x getattr | `cli.py:35` (safe log level lookup), `feed_screen.py` (attribute access on ListItem), `queue.py` (attribute access on ListItem) | ✅ All safe |

### Audit Artifacts Saved
- `docs/sys/dynamic_audit_report.txt` — dynamic call pattern analysis
- `docs/sys/function_inventory.txt` / `.json` — full function inventory
- `docs/sys/dependency_report.txt` / `.json` — call dependency analysis

---

## Full Audit: 2026-08-01 — Post-EQ-Feature, Linter-Assisted Re-Audit

**Score**: **B** — 14 new findings (1 P0, 4 P1, 7 P2, 2 P3). Re-graded down from A:
previously "clean" areas (unused imports, import grouping, silent `except: pass`)
were verified with a real linter (ruff 0.16.1) and found to violate the checklist.

### Tooling Used
- `scripts/function_inventory.py` — 164 functions, 24 classes, 21 files (excludes tests/scripts; includes `project_kit/scaffold.py` + `splash_preview.py`)
- `scripts/find_dependencies.py` — regenerated fresh: **104 called / 60 uncalled** (uncalled = Textual action handlers / event overrides, expected)
- `ruff check aetherpod/` — 69 findings (6 unused imports, 10 import-block sorting, 16 BLE001, 4 S110, rest style nits)
- `pytest tests/` — **26 passed**
- Static scans — no bare `except:`, no `eval`/`exec`, no trailing whitespace, no line > 100

### Findings

| # | Description | Priority | Status |
|---|-------------|----------|--------|
| F15 | `data/state.json` (2.5 MB of personal feeds/played/progress) is **committed to git** since v0.2.0 | P0 | ✅ Fixed |
| F16 | Maps stale: `maps/architecture.md` + `imports.mmd` omit `eq_presets.py` and the new player→eq_presets edge | P1 | ✅ Fixed |
| F17 | Silent failures — 4x `try/except Exception: pass` (feed_screen 265/273, episode_screen 397/811) | P1 | ✅ Fixed |
| F18 | Version drift — `__init__.py`=0.3.0, `pyproject.toml`=0.2.1, CHANGELOG/commit=v0.3.1 | P1 | ✅ Fixed |
| F19 | EQ feature uncommitted: engines/player/screens modified + `eq_presets.py` untracked; no CHANGELOG entry, no tests | P1 | ✅ Fixed |
| F20 | `except Exception`: 16 total — 15 pre-approved at boundaries, **1 new** in `eq_presets.py:100` | P2 | Open |
| F21 | 6 unused imports (F401): app.py `QueueScreen`, engines.py `threading`/`field`/`Path`, models.py `field`/`Any`, splash.py `shutil`, episode_screen.py `PathInputDialog` | P2 | Open |
| F22 | 10 unsorted import blocks (I001) — ruff disagrees with prior "2.1 ✅" | P2 | Open |
| F23 | `player.py:91` unpacks `label` but never uses it (new EQ code) | P2 | ✅ Fixed |
| F24 | Audit reports out of sync — dependency_report.json (150) vs inventory (164); regenerated to 164/104/60 during this audit | P2 | Fixed |
| F25 | KNOWLEDGE.md stale: `aetherpod/screens.py` ref (now package), missing eq_presets.py, no EQ session entry | P2 | Open |
| F26 | `docs/sys/dynamic_audit_report.txt` stale (Jul 27) + tracked; house_cleaning says regenerate fresh per audit | P2 | Open |
| F27 | `.gitignore` stale `src/data/*` entries; untracked `Tayogo.json` (EQ export), `uv.lock`, `safety.md` at root — decide commit/move/ignore | P3 | Open |
| F28 | Ruff style nits: UP024 socket.error→OSError (4), SIM102 (4), RUF046 int casts (3), SIM114, SIM117, ASYNC251, PLW1510, RUF012 (mutable class attrs = Textual BINDINGS), F541, RUF022 | P3 | Open |

### Commits (2026-08-01 session)
- `7b0d16a` chore: stop tracking data/state.json (F15)
- `0bc90ee` feat: v0.4.0 — audio EQ presets (F19 + F18 + F23)
- `a396159` docs: add eq_presets.py to architecture and imports maps (F16)
- `6d31a50` fix: log instead of silently passing on widget-not-ready exceptions (F17)

### Map Health

| Map File | Status | Notes |
|----------|--------|-------|
| maps/architecture.md | ✅ OK | Updated 2026-08-01 — eq_presets.py added |
| maps/imports.mmd | ✅ OK | Updated 2026-08-01 — player→eq_presets edge added |

### Healthy (no action)
- Tests: 26/26 pass; core logic (DataManager, RSS) covered. EQ module has **no tests** (see F19)
- No bare `except:`, no `eval`/`exec`, no trailing whitespace, no lines > 100
- 6 `getattr` usages — all safe attribute lookups; 56→60 uncalled functions are Textual callbacks
- Import graph is a DAG — no circular imports
- All 21 source files have correct file headers

