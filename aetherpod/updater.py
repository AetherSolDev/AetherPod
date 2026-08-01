# Created: 2026-08-01
# Last Edited: 2026-08-01 12:08 CT (America/Chicago)
# Path: aetherpod/updater.py
# Purpose: Background update checker — compares installed version to latest GitHub release.

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import aiohttp

from aetherpod import __version__

logger = logging.getLogger(__name__)

_RELEASES_API = "https://api.github.com/repos/AetherSolDev/AetherPod/releases/latest"
"""GitHub API endpoint for the latest release (public repo, no auth needed)."""

_TIMEOUT_SECONDS = 5
"""Network timeout for the version check.  Slow/failing requests must not block the TUI."""


@dataclass(frozen=True)
class UpdateCheck:
    """Result of a background update check."""

    available: bool
    latest: str = ""
    current: str = __version__

    @property
    def message(self) -> str:
        if self.available:
            return (
                f"Update available: v{self.latest} (you have v{self.current}). "
                "Quit and run 'aetherpod -u' to upgrade."
            )
        return f"You're on the latest version (v{self.current})."


def _version_tuple(version: str) -> tuple[int, ...]:
    """Parse ``0.4.3`` (or ``v0.4.3``) into a comparable int tuple.

    Non-numeric suffixes (e.g. ``0.4.3-rc1``) are ignored for ordering.
    """
    cleaned = version.lstrip("vV").split("-", 1)[0]
    parts: list[int] = []
    for part in cleaned.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer_than(latest: str, current: str) -> bool:
    """Return True if *latest* is a newer version than *current*."""
    return _version_tuple(latest) > _version_tuple(current)


async def fetch_latest_release(session: aiohttp.ClientSession) -> str:
    """Fetch the latest release tag name (e.g. ``0.4.3``) from GitHub.

    Raises on network/HTTP errors so the caller can fail silently.
    """
    async with session.get(_RELEASES_API) as resp:
        resp.raise_for_status()
        data = await resp.json()
        tag: str = data.get("tag_name", "") or ""
        return tag.lstrip("vV")


async def check_for_update() -> UpdateCheck:
    """Check GitHub for a newer release.  Never raises; offline = no update.

    Falls back to ``UpdateCheck(available=False)`` on any network, HTTP, or
    parse error, logging at DEBUG so a missing connection is completely silent.
    """
    try:
        timeout = aiohttp.ClientTimeout(total=_TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            latest = await fetch_latest_release(session)
        if not latest:
            return UpdateCheck(available=False)
        return UpdateCheck(
            available=is_newer_than(latest, __version__),
            latest=latest,
            current=__version__,
        )
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
        logger.debug("Update check skipped: %s", exc)
        return UpdateCheck(available=False)
