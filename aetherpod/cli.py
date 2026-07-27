# Created: 2026-07-25
# Last Edited: 2026-07-27 16:09 CT (America/Chicago)
# Path: aetherpod/cli.py
# Purpose: CLI entry point logic — argparse, logging setup, headless commands, TUI launch.

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

from platformdirs import user_state_dir

from aetherpod.engine import DataManager
from aetherpod.rss import fetch_feed
from aetherpod import __version__

_UPGRADE_URL = "git+https://github.com/brandonmunoz1975-ops/AetherPod.git"
"""Default pip source for ``--upgrade``."""

_SCRIPT_DIR = Path(__file__).resolve().parent.parent

_LOG_DIR = Path(user_state_dir("aetherpod", ensure_exists=True)) / "log"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_LOG_LEVEL = os.environ.get("AETHERPOD_LOG_LEVEL", "INFO").upper()

_LOG_FILE = _LOG_DIR / "aetherpod.log"

_log_level = getattr(logging, _LOG_LEVEL, logging.INFO)

_log_stderr = logging.StreamHandler(stream=sys.stderr)
_log_stderr.setLevel(logging.WARNING)

logging.basicConfig(
    level=_log_level,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    handlers=[
        _log_stderr,
        logging.FileHandler(str(_LOG_FILE), encoding="utf-8", delay=False),
    ],
)
logger = logging.getLogger("aetherpod")
logger.info("Logging to %s", _LOG_FILE)


def _default_data_path() -> str:
    # None = let DataManager use platformdirs default
    return ""


def cmd_list(data: DataManager) -> None:
    for url in data.get_feeds():
        result = fetch_feed(url)
        if result.error:
            print(f"  \u2717 {url} \u2014 {result.error}")
        else:
            played = sum(1 for e in result.episodes if data.is_played(e.episode_id or ""))
            print(f"  {result.title} ({len(result.episodes)} ep, {played} played)")
            print(f"    {url}")


def cmd_add(data: DataManager, url: str) -> None:
    if data.add_feed(url):
        print(f"Added feed: {url}")
    else:
        print(f"Feed already subscribed: {url}")


def cmd_refresh(data: DataManager) -> None:
    for url in data.get_feeds():
        result = fetch_feed(url)
        if result.error:
            print(f"\u2717 {url}: {result.error}")
            continue
        print(f"\n=== {result.title} ===")
        for ep in result.episodes[:5]:
            played = "\u2713" if data.is_played(ep.episode_id or "") else " "
            print(f"  [{played}] {ep.title}")


def cmd_import_opml(data: DataManager, path: str) -> None:
    count = data.opml_import(path)
    print(f"Imported {count} feed(s) from {path}")


def cmd_export_opml(data: DataManager, path: str) -> None:
    count = data.opml_export(path)
    print(f"Exported {count} feed(s) to {path}")


def _pip_cmd(subcmd: list[str]) -> list[str]:
    """Build a pip command, adding ``--break-system-packages`` if outside a venv."""
    cmd = [sys.executable, "-m", "pip"] + subcmd
    if sys.prefix == sys.base_prefix:
        cmd.append("--break-system-packages")
    return cmd


def _run_pip(cmd: list[str]) -> None:
    """Run a pip command, capturing output for error reporting."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
            result.check_returncode()
    except subprocess.CalledProcessError as exc:
        print(f"pip command failed: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_upgrade(url: str | None = None) -> None:
    """Upgrade AetherPod to the latest version.

    For editable installs, runs ``git pull`` in the project directory
    and re-installs.  For non-editable installs, runs ``pip install --upgrade``
    from the GitHub repo (or a custom *url*).
    """
    pip_source = url or _UPGRADE_URL

    try:
        dist = distribution("aetherpod")
        direct_url_str = dist.read_text("direct_url.json") if dist else None
    except (PackageNotFoundError, FileNotFoundError):
        direct_url_str = None

    editable = False
    if direct_url_str:
        info = json.loads(direct_url_str)
        editable = info.get("dir_info", {}).get("editable", False)

    if editable:
        print(f"AetherPod {__version__} — installed in editable mode.")
        print("Attempting git pull in the project directory...")
        try:
            subprocess.check_call(["git", "pull"], cwd=_SCRIPT_DIR)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            print(f"Git pull failed: {exc}", file=sys.stderr)
            print("Manually: cd AetherPod && git pull && pip install -e .")
            sys.exit(1)
        cmd = _pip_cmd(["install", "-e", str(_SCRIPT_DIR)])
        _run_pip(cmd)
        print(f"Upgraded to AetherPod {__version__}")
        return

    print(f"Upgrading AetherPod from {pip_source}...")
    cmd = _pip_cmd(["install", "--upgrade", pip_source])
    _run_pip(cmd)
    print("Upgrade complete.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="aetherpod", description="Terminal podcast manager")
    default_data = str(_default_data_path())
    parser.add_argument("--data", default=default_data,
                        help="Path to state file (default: XDG state dir)")
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    parser.add_argument("--upgrade", action="store_true",
                        help="Upgrade AetherPod to the latest version")
    parser.add_argument("--upgrade-url",
                        help="Custom pip-compatible URL for upgrade source (requires --upgrade)")

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="List subscribed feeds")
    sub.add_parser("tui", help="Launch the TUI (default)")
    add_p = sub.add_parser("add", help="Subscribe to a feed URL")
    add_p.add_argument("url")
    sub.add_parser("refresh", help="Fetch all feeds and show episodes")
    sub.add_parser("reset", help="Clear all state")
    import_p = sub.add_parser("import", help="Import feeds from OPML file")
    import_p.add_argument("path", help="Path to OPML file")
    export_p = sub.add_parser("export", help="Export feeds to OPML file")
    export_p.add_argument("path", help="Output path for OPML file")

    args = parser.parse_args()

    if args.version:
        print(f"AetherPod {__version__}")
        return

    if args.upgrade:
        cmd_upgrade(args.upgrade_url)
        return

    data_path = None
    if args.data:
        p = Path(args.data)
        if not p.is_absolute():
            p = (_SCRIPT_DIR / args.data).resolve()
        data_path = p
    data = DataManager(data_path)

    if args.command == "list":
        cmd_list(data)
    elif args.command == "add":
        cmd_add(data, args.url)
    elif args.command == "refresh":
        cmd_refresh(data)
    elif args.command == "import":
        cmd_import_opml(data, args.path)
    elif args.command == "export":
        cmd_export_opml(data, args.path)
    elif args.command == "reset":
        print(f"Reset: removing {data._path}")
        data._path.unlink(missing_ok=True)
        data.load()
    else:
        from aetherpod.app import AetherPod

        app = AetherPod(data_path=data_path)
        app.run()


if __name__ == "__main__":
    main()
