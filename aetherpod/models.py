# Created: 2026-07-27
# Last Edited: 2026-07-27 15:54 CT (America/Chicago)
# Path: aetherpod/models.py
# Purpose: Shared dataclasses — Episode, ProgressInfo, FeedResult.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Episode:
    """Represents a single podcast episode from an RSS feed."""

    title: str
    url: str
    published: str | None = None
    summary: str | None = None
    duration: str | None = None
    episode_id: str | None = None


@dataclass
class ProgressInfo:
    """Playback progress for a partially-listened episode."""

    position: float = 0.0
    total_length: float = 0.0


@dataclass
class FeedResult:
    """Result of fetching and parsing an RSS feed."""

    title: str
    episodes: list[Episode]
    error: str | None = None
    not_modified: bool = False
    etag: str = ""
    last_modified: str = ""
