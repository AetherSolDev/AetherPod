# Created: 2026-07-19
# Last Edited: 2026-07-25 09:01 CT (America/Chicago)
# Path: aetherpod.py
# Purpose: Thin entry point — delegates to src.cli.main().

from __future__ import annotations

import sys

if __name__ == "__main__":
    from src.cli import main
    sys.exit(main())
