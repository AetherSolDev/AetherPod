# Created: 2026-07-19
# Last Edited: 2026-07-27 16:09 CT (America/Chicago)
# Path: aetherpod.py
# Purpose: Thin entry point — delegates to src.cli.main().

from __future__ import annotations

import sys

if __name__ == "__main__":
    from aetherpod.cli import main
    sys.exit(main())
