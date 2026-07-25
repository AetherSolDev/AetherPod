# Created: 2026-07-20
# Last Edited: 2026-07-24 17:01 CT (America/Chicago)
# Path: docs/INSTALL.md
# Purpose: Installation instructions for AetherPod.

# AetherPod — Installation Guide

## Prerequisites

- **Python 3.14+** (AetherPod uses modern Python features)
- **mpv** — the media player that AetherPod controls
- **pip** (included with Python)

## Install mpv

### Arch Linux

```bash
sudo pacman -S mpv
```

### Debian / Ubuntu

```bash
sudo apt install mpv
```

### macOS (Homebrew)

```bash
brew install mpv
```

### Windows (Scoop)

```powershell
scoop install mpv
```

Other platforms: see [mpv.io](https://mpv.io/installation/)

## Install AetherPod

### 1. Clone the repository

```bash
git clone https://github.com/your-username/AetherPod.git
cd AetherPod
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate   # Linux/macOS
# venv\Scripts\activate    # Windows
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Run AetherPod

```bash
aetherpod
```

Or launch the TUI directly:

```bash
aetherpod tui
```

## Optional: System-wide install

```bash
pip install .
```

Then run from anywhere:

```bash
aetherpod
```

## Verify it works

```bash
aetherpod --version
```

You should see: `AetherPod 0.2.0`
