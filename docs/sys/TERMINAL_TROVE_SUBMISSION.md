# Created: 2026-08-05
# Last Edited: 2026-08-05 12:51 CT (America/Chicago)
# Path: docs/sys/TERMINAL_TROVE_SUBMISSION.md
# Purpose: Pre-filled "Post a Tool" submission for Terminal Trove (https://terminaltrove.com/post/).

# AetherPod — Terminal Trove Submission

Criteria check:
1. Cross platform — yes (Linux, macOS, Windows).
2. Standalone binaries — yes (PyInstaller executables on GitHub Releases; no Python/pip needed).
3. Image preview — yes: `assets/screens/splash.png`, `episodes.png`, `playing.png`, `details.png` (PNG). A GIF preview would be ideal but is optional.
4. Does not already exist — verified: the only podcast tools on Terminal Trove are `castero` and `podliner`. AetherPod is not listed.

---

## Basic Info

| Field | Value |
|-------|-------|
| name | `aetherpod` |
| url | `github.com/AetherSolDev/AetherPod` |
| tagline | Subscribe, browse, and play podcasts from your terminal — a Textual TUI podcast manager. |

### Description (250–300 chars required) — ~283 chars
> AetherPod is a full-featured terminal podcast manager built on the Textual framework. Subscribe to any RSS/Atom podcast feed, browse episodes in a sortable data table, and play them through mpv, VLC, or ffplay. It resumes playback where you left off, tracks played episodes, and keeps all state in a portable JSON file — a fast, keyboard-driven alternative to GUI podcast apps.

### 2–3 Standout Features (150–300 chars required) — ~210 chars
> Playback resumes exactly where you left off with live progress bars in the episode table. Cross-feed search finds any episode in your whole library instantly. Audio EQ presets (mpv) tailor voice clarity with the 1–4 keys, and a play queue auto-advances to the next episode.

### Other Notable Features (optional, 150–300 chars) — ~257 chars
> OPML import/export for migrating from other podcast apps, sortable and filterable zebra-striped feed list, dark/light theme toggle, animated splash screen with subscription stats, conditional-GET refresh (ETag/Last-Modified), and single-file executables for Linux, macOS (arm64 + Intel), and Windows.

### Who is this for / When to use it (150–250 chars required) — ~235 chars
> Daily podcast listeners who live in the terminal and want a distraction-free way to subscribe, browse, and play shows without opening a GUI. Great on servers, over SSH, or on minimalist setups — the entire library is a few keypresses away, and state rides along on a USB stick.

---

## Technical Details

| Field | Value |
|-------|-------|
| primary language | python |
| license | gpl-3.0 |

### Categories
- Operating Systems: `linux`, `macos`, `windows`
- UI & Display: `tui`, `textualize`
- General: `music`, `cross-platform`

---

## Image Preview

| File | Size |
|------|------|
| `assets/screens/aetherpod-demo.gif` | 1900×1000, 799 KB — **recommended preview** (full demo: splash → feed list → episodes → details → search → theme) |
| `assets/screens/splash.png` | 1221×405, 78 KB |
| `assets/screens/episodes.png` | 1255×435, 232 KB |
| `assets/screens/playing.png` | 1340×540, 222 KB |
| `assets/screens/details.png` | 1302×877, 538 KB |

Raw URLs for upload (or host elsewhere):
- https://raw.githubusercontent.com/AetherSolDev/AetherPod/main/assets/screens/aetherpod-demo.gif
- https://raw.githubusercontent.com/AetherSolDev/AetherPod/main/assets/screens/splash.png
- https://raw.githubusercontent.com/AetherSolDev/AetherPod/main/assets/screens/episodes.png
- https://raw.githubusercontent.com/AetherSolDev/AetherPod/main/assets/screens/playing.png
- https://raw.githubusercontent.com/AetherSolDev/AetherPod/main/assets/screens/details.png

> The GIF preview satisfies Terminal Trove's "GIF recommended" guidance. The recording was produced with charmbracelet/VHS and lives at `assets/screens/aetherpod-demo.gif`. The `.tape` source is under `/tmp/opencode/aetherpod-demo/aetherpod.tape` (local; not committed — regenerate via `vhs aetherpod.tape` with a local RSS server + seeded `state.json`).

---

## Install Instructions

> Note: AetherPod is **not** in package repositories yet. Terminal Trove asks that tools exist in repos, but prebuilt binaries + git install satisfy "standalone binaries preferred." AUR packaging is blocked at present — see the "AUR Packaging" section below. If the curator rejects on this point, the fix is packaging (AUR/formula) — tracked as future work.

### Linux (x86_64) — prebuilt binary
```sh
curl -Lo aetherpod https://github.com/AetherSolDev/AetherPod/releases/latest/download/aetherpod-linux
chmod +x aetherpod && ./aetherpod
```

### macOS (Apple Silicon / Intel)
```sh
curl -Lo aetherpod https://github.com/AetherSolDev/AetherPod/releases/latest/download/aetherpod-macos-arm64   # or aetherpod-macos-x86_64
chmod +x aetherpod
xattr -d com.apple.quarantine aetherpod   # Gatekeeper bypass for unsigned binary
./aetherpod
```

### Windows (x86_64)
```powershell
curl -Lo aetherpod-windows.exe https://github.com/AetherSolDev/AetherPod/releases/latest/download/aetherpod-windows.exe
.\aetherpod-windows.exe
```

### Any platform — from source (Python 3.9+, needs mpv/VLC/ffplay)
```sh
git clone https://github.com/AetherSolDev/AetherPod.git
cd AetherPod
bash scripts/install.sh        # interactive: system-wide, user-local, or venv
# or: make install             # system-wide
# or: make install-user        # ~/.local, no root
# or: pip install git+https://github.com/AetherSolDev/AetherPod.git
```

---

## Author & Confirmation

- **Are you the author?** yes
- **Email:** (user to fill in before submitting)
- **Confirm criteria read:** yes

---

## AUR Packaging (status: BLOCKED)

**Verified 2026-08-05:** Arch Linux officially paused AUR new submissions. See https://archlinux.org/news/active-aur-malicious-packages-incident/ (2026-06-12): "We are currently experiencing a high volume of malicious package adoptions and updates in the Arch User Repository... users may see issues with: creating new accounts on the AUR, pushing package updates, adopting or creating new packages."

So new-package creation is throttled/blocked while Arch builds a permanent solution. **A PKGBUILD should still be prepared now so it can be submitted the moment new-package creation reopens.**

### Steps to submit when reopened
1. Create an AUR account at https://aur.archlinux.org (register SSH key per https://wiki.archlinux.org/title/AUR_submission_guidelines#Authentication).
2. `git clone ssh://aur@aur.archlinux.org/aetherpod.git` (this pre-creates the repo).
3. Add `PKGBUILD` + `.SRCINFO` (+ optional `.install`), commit, push.
4. `.SRCINFO` generated with `makepkg --printsrcinfo > .SRCINFO` (requires `pkgctl` / `makepkg`).
5. Package name must be lowercase (`aetherpod`); no `-git` suffix needed since releases are tagged.

### Draft PKGBUILD (source-based, GPLv3, Python)
```bash
# Maintainer: AetherSol <support@aethersol.io>
pkgname=aetherpod
pkgver=0.4.4
pkgrel=1
pkgdesc="Terminal Podcast Manager — subscribe, browse, and play podcasts from your terminal"
arch=('any')
url="https://github.com/AetherSolDev/AetherPod"
license=('GPL3')
depends=('python' 'mpv' 'python-feedparser' 'python-textual' 'python-aiohttp')
makedepends=('python-build' 'python-installer' 'python-wheel' 'python-setuptools')
source=("$pkgname-$pkgver.tar.gz::https://github.com/AetherSolDev/AetherPod/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')  # replace with real hash after downloading
build() {
  cd "$srcdir/AetherPod-$pkgver"
  python -m build --wheel --no-isolation
}
package() {
  cd "$srcdir/AetherPod-$pkgver"
  python -m installer --destdir="$pkgdir" dist/*.whl
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
```
> Note: `depends` includes `mpv` (or `vlc`) — the audio backend. `python-feedparser`/`python-textual`/`python-aiohttp` must exist in the Arch repos (all do). `arch=('any')` since it's pure Python. Optional deps: `vlc` for the VLC backend on systems without mpv.

---

## Suggested Social Blurb (optional, for the submission email / posting)

> AetherPod — Terminal Podcast Manager. Subscribe, browse, and play podcasts from your terminal. Textual TUI, mpv/VLC/ffplay backends, resume playback, cross-feed search, EQ presets, OPML import/export, single-file binaries for Linux/macOS/Windows. BTW.. I use Arch. https://github.com/AetherSolDev/AetherPod
