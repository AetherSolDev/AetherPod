# Created: 2026-07-19
# Last Edited: 2026-07-25 14:18 CT (America/Chicago)
# Path: src/engine.py
# Purpose: Core data engine — DataManager for state persistence and RSS feed fetching.

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import threading
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from email import utils as email_utils
from pathlib import Path
from typing import Any

from platformdirs import user_state_dir

logger = logging.getLogger(__name__)

# ── constants ──────────────────────────────────────────────────────

REFRESH_DAYS = 100
"""Default number of days of episodes to show on auto-refresh.

Automatic refreshes (startup, feed add/remove) only fetch episodes
from the last *REFRESH_DAYS* to keep the list manageable.  A manual
full refresh (``u`` key) omits this limit."""


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


class DataManager:
    """Manages persistent state: feed URLs, played-episode history, and playback progress.

    Reads/writes a JSON file at the configured path. Thread-safe for
    single-process use via an internal lock.
    """

    STATE_VERSION = 1
    """Current schema version for ``state.json``.

    Increment this when making backward-incompatible changes to the
    persisted data format.  Migration functions (see ``_MIGRATIONS``)
    are run automatically on load when the stored version is lower.
    """

    MAX_PLAYED = 50  # rolling limit for played_episodes + progress entries

    # ── schema migration ──────────────────────────────────────────

    _MIGRATIONS: dict[int, callable] = {}
    """Registry of migration functions keyed by *from* version.

    Each function receives the raw ``dict`` loaded from disk and
    returns a migrated ``dict``.  Migrations are run in sequence
    from the stored version up to ``STATE_VERSION - 1``.
    The registry is populated dynamically in ``_register_migrations``.
    """

    @staticmethod
    def _migrate_v0_to_v1(data: dict) -> dict:
        """Migrate from schema version 0 (no version key) to version 1.

        Version 0 state has all fields already in their current form
        (feeds, played_episodes, episode_progress, feed_headers,
        feed_cache).  This migration is a no-op — it only sets the
        version marker so subsequent migrations can assume it's present.
        """
        data.setdefault("feeds", [])
        data.setdefault("played_episodes", [])
        data.setdefault("episode_progress", {})
        data.setdefault("feed_headers", {})
        data.setdefault("feed_cache", {})
        return data

    # ── persistence ────────────────────────────────────────────────

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            path = Path(user_state_dir("aetherpod", ensure_exists=True)) / "state.json"
        self._path = Path(path)
        self._lock = threading.Lock()
        self._feeds: list[str] = []
        self._played: set[str] = set()
        self._played_order: list[str] = []
        self._progress: dict[str, dict[str, float]] = {}
        self._feed_headers: dict[str, dict[str, str]] = {}
        self._feed_cache: dict[str, dict[str, Any]] = {}
        self._refresh_days: int = REFRESH_DAYS
        self._register_migrations()
        self.load()

    def _register_migrations(self) -> None:
        """Populate the class-level migration registry."""
        # Clear registry and re-register static methods
        type(self)._MIGRATIONS = {
            0: self._migrate_v0_to_v1,
        }

    def load(self) -> None:
        """Load state from disk. If the file is missing or corrupt, start empty.

        Runs schema migrations automatically when the stored version is
        older than ``STATE_VERSION``.  Each migration step is logged at
        INFO level for audit.
        """
        with self._lock:
            if not self._path.exists():
                logger.info("No state file at %s — starting fresh", self._path)
                self._feeds = []
                self._played = set()
                self._played_order = []
                self._progress = {}
                self._feed_headers = {}
                self._feed_cache = {}
                return

            try:
                raw = self._path.read_text(encoding="utf-8")
                data: dict[str, Any] = json.loads(raw)

                # ── schema migration ─────────────────────────────────
                stored_version = data.get("version", 0)
                if stored_version < self.STATE_VERSION:
                    logger.info(
                        "State schema version %d → %d: running %d migration(s)",
                        stored_version, self.STATE_VERSION,
                        self.STATE_VERSION - stored_version,
                    )
                for v in range(stored_version, self.STATE_VERSION):
                    mig = type(self)._MIGRATIONS.get(v)
                    if mig:
                        data = mig(data)
                        logger.info("Migration %d → %d applied", v, v + 1)
                data["version"] = self.STATE_VERSION

                self._feeds = data.get("feeds", [])
                played_raw = data.get("played_episodes", [])
                self._progress = data.get("episode_progress", {})
                self._feed_headers = data.get("feed_headers", {})
                self._feed_cache = data.get("feed_cache", {})
                self._refresh_days = data.get("refresh_days", REFRESH_DAYS)
                if isinstance(played_raw, list):
                    self._played = set(played_raw)
                    self._played_order = list(dict.fromkeys(played_raw))  # dedupe, preserve order
                else:
                    self._played = set()
                    self._played_order = []
                logger.debug("Loaded %d feeds, %d played, %d with progress, %d cached, %d headers",
                             len(self._feeds), len(self._played), len(self._progress),
                             len(self._feed_cache), len(self._feed_headers))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load state: %s — starting fresh", exc)
                self._feeds = []
                self._played = set()
                self._played_order = []
                self._progress = {}
                self._feed_headers = {}
                self._feed_cache = {}

    def save(self) -> None:
        """Persist current state to disk atomically."""
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": self.STATE_VERSION,
                "feeds": list(self._feeds),
                "played_episodes": list(self._played_order),
                "episode_progress": dict(self._progress),
                "feed_headers": dict(self._feed_headers),
                "refresh_days": self._refresh_days,
                "feed_cache": dict(self._feed_cache),
            }
            tmp = self._path.with_suffix(".tmp")
            try:
                tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
                tmp.replace(self._path)
            except OSError as exc:
                logger.error("Failed to save state: %s", exc)
                raise

    # ── feed management ────────────────────────────────────────────

    def add_feed(self, url: str) -> bool:
        """Add a feed URL if not already present. Returns True if added."""
        if url in self._feeds:
            return False
        self._feeds.append(url)
        self.save()
        logger.info("Added feed: %s", url)
        return True

    def remove_feed(self, url: str) -> bool:
        """Remove a feed URL. Returns True if it existed."""
        if url not in self._feeds:
            return False
        self._feeds.remove(url)
        self._feed_cache.pop(url, None)
        self._feed_headers.pop(url, None)
        self.save()
        logger.info("Removed feed: %s", url)
        return True

    def get_feeds(self) -> list[str]:
        """Return a copy of the feed URL list."""
        return list(self._feeds)

    def get_refresh_days(self) -> int:
        """Return the configured refresh window in days."""
        return self._refresh_days

    def set_refresh_days(self, days: int) -> None:
        """Set the refresh window and persist."""
        self._refresh_days = max(1, days)

    # ── episode tracking ───────────────────────────────────────────

    def mark_played(self, episode_id: str) -> bool:
        """Mark an episode as played. Returns True if newly marked."""
        with self._lock:
            if episode_id in self._played:
                return False
            self._played.add(episode_id)
            self._played_order.append(episode_id)
            self._enforce_retention()
        self.save()
        logger.debug("Marked played: %s", episode_id)
        return True

    def is_played(self, episode_id: str) -> bool:
        """Check if an episode has been played (thread-safe)."""
        with self._lock:
            return episode_id in self._played

    def unmark_played(self, episode_id: str) -> bool:
        """Unmark an episode as played, so it appears unplayed again.

        Also removes any saved progress for the episode.  Returns True
        if the episode was previously marked played.
        """
        with self._lock:
            if episode_id not in self._played:
                return False
            self._played.discard(episode_id)
            self._played_order = [e for e in self._played_order if e != episode_id]
            self._progress.pop(episode_id, None)
        self.save()
        logger.debug("Unmarked played: %s", episode_id)
        return True

    def get_played(self) -> set[str]:
        """Return a copy of the played-episode set."""
        with self._lock:
            return set(self._played)

    # ── progress tracking ──────────────────────────────────────────

    def save_progress(self, episode_id: str, position: float, total_length: float) -> None:
        """Save playback progress for an episode.

        If *position* is within 5 seconds of *total_length*, the episode
        is also marked as played (completion heuristic).  Thread-safe.
        """
        with self._lock:
            self._progress[episode_id] = {"position": position, "total_length": total_length}
            if total_length > 0 and position >= total_length - 5:
                if episode_id not in self._played:
                    self._played.add(episode_id)
                    self._played_order.append(episode_id)
            self._enforce_retention()
        self.save()
        logger.debug("Progress saved for %s: pos=%.1f len=%.1f", episode_id, position, total_length)

    def get_progress(self, episode_id: str) -> ProgressInfo | None:
        """Return playback progress for an episode, or ``None``."""
        with self._lock:
            entry = self._progress.get(episode_id)
        if entry is None:
            return None
        return ProgressInfo(position=entry.get("position", 0), total_length=entry.get("total_length", 0))

    # ── conditional fetch headers ────────────────────────────────────

    def get_feed_headers(self, url: str) -> dict[str, str]:
        """Return stored ETag/Last-Modified headers for a feed URL."""
        with self._lock:
            return dict(self._feed_headers.get(url, {}))

    def save_feed_headers(self, url: str, etag: str = "", last_modified: str = "") -> None:
        """Persist ETag and/or Last-Modified for a feed URL."""
        with self._lock:
            headers: dict[str, str] = {}
            if etag:
                headers["etag"] = etag
            if last_modified:
                headers["last_modified"] = last_modified
            if headers:
                self._feed_headers[url] = headers
            else:
                self._feed_headers.pop(url, None)
        self.save()

    # ── feed result cache ────────────────────────────────────────────

    def get_cached_result(self, url: str) -> FeedResult | None:
        """Return a cached ``FeedResult`` for *url*, or ``None``."""
        with self._lock:
            entry = self._feed_cache.get(url)
        if entry is None:
            return None
        episodes = [
            Episode(
                title=e.get("title", "(no title)"),
                url=e.get("url", ""),
                published=e.get("published"),
                summary=e.get("summary"),
                duration=e.get("duration"),
                episode_id=e.get("episode_id"),
            )
            for e in entry.get("episodes", [])
        ]
        return FeedResult(title=entry.get("title", url), episodes=episodes)

    def save_cached_result(self, url: str, result: FeedResult) -> None:
        """Cache a successful ``FeedResult`` for *url*."""
        if result.error or result.not_modified:
            return
        entry: dict[str, Any] = {
            "title": result.title,
            "episodes": [
                {
                    "title": e.title,
                    "url": e.url,
                    "published": e.published,
                    "summary": e.summary,
                    "duration": e.duration,
                    "episode_id": e.episode_id,
                }
                for e in result.episodes
            ],
        }
        with self._lock:
            self._feed_cache[url] = entry
        self.save()

    # ── retention ──────────────────────────────────────────────────

    def _enforce_retention(self) -> None:
        """Trim the oldest entries when the played list exceeds MAX_PLAYED.

        Caller must hold ``_lock``.  Removes excess entries from
        ``_played``, ``_played_order``, and ``_progress``.
        """
        excess = len(self._played_order) - self.MAX_PLAYED
        if excess <= 0:
            return
        for epid in self._played_order[:excess]:
            self._played.discard(epid)
            self._progress.pop(epid, None)
        self._played_order = self._played_order[excess:]
        logger.debug("Retention: trimmed %d old entries", excess)

    # ── OPML import / export ──────────────────────────────────────────

    def opml_import(self, file_path: str | Path) -> int:
        """Import feed URLs from an OPML file.

        Parses the OPML 1.0/2.0 XML structure and extracts every
        ``<outline>`` element with an ``xmlUrl`` attribute.  URLs that
        are not already subscribed are added via :meth:`add_feed`.

        Returns the number of *new* feeds added (omitting duplicates).
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning("OPML file not found: %s", path)
            return 0

        try:
            tree = ET.parse(path)
            root = tree.getroot()
        except (ET.ParseError, OSError) as exc:
            logger.error("Failed to parse OPML %s: %s", path, exc)
            return 0

        count = 0
        for outline in root.iter("outline"):
            url = outline.get("xmlUrl", "")
            if url and self.add_feed(url):
                count += 1

        logger.info("Imported %d new feeds from %s", count, path)
        return count

    def opml_export(self, file_path: str | Path) -> int:
        """Export subscribed feeds to an OPML 2.0 file.

        Generates a standard OPML 2.0 document containing the current
        list of feed URLs as ``<outline>`` elements, then writes it to
        *file_path*.

        Returns the number of feeds exported.
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        opml = ET.Element("opml", version="2.0")
        head = ET.SubElement(opml, "head")
        title = ET.SubElement(head, "title")
        title.text = "AetherPod subscriptions"
        body = ET.SubElement(opml, "body")

        for feed_url in self._feeds:
            outline = ET.SubElement(body, "outline")
            outline.set("text", feed_url)
            outline.set("title", feed_url)
            outline.set("type", "rss")
            outline.set("xmlUrl", feed_url)

        tree = ET.ElementTree(opml)
        # Indent for readability on Python 3.9+
        ET.indent(tree, space="  ")

        try:
            tree.write(str(path), encoding="utf-8", xml_declaration=True)
        except OSError as exc:
            logger.error("Failed to write OPML %s: %s", path, exc)
            return 0

        count = len(self._feeds)
        logger.info("Exported %d feeds to %s", count, path)
        return count


# ── RSS fetching ───────────────────────────────────────────────────

def fetch_feed(url: str, timeout: int = 15,
              etag: str = "", last_modified: str = "") -> FeedResult:
    """Parse an RSS/Atom feed and return structured episode data.

    Fetches the feed with a *timeout* (seconds) using urllib, then
    parses with feedparser. Pass *etag* and/or *last_modified* to
    perform a conditional GET — if the server returns 304 (Not Modified),
    ``FeedResult.not_modified`` is set to ``True`` and no parsing occurs.

    Returns a FeedResult with episodes or an error description on failure.
    """
    import feedparser  # lazy import — optional dependency

    # Fetch the feed data ourselves so we can set a timeout
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AetherPod/1.0"})
        if etag:
            req.add_header("If-None-Match", etag)
        if last_modified:
            req.add_header("If-Modified-Since", last_modified)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            new_etag = resp.headers.get("ETag", "")
            new_lm = resp.headers.get("Last-Modified", "")
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            logger.debug("Feed unchanged (304): %s", url)
            return FeedResult(title="", episodes=[], not_modified=True)
        logger.error("HTTP %d for %s: %s", exc.code, url, exc.reason)
        return FeedResult(title="", episodes=[], error=f"HTTP {exc.code}: {exc.reason}")
    except urllib.error.URLError as exc:
        logger.error("URL error for %s: %s", url, exc.reason)
        return FeedResult(title="", episodes=[], error=str(exc.reason))
    except TimeoutError:
        logger.error("Timeout fetching %s (%ds)", url, timeout)
        return FeedResult(title="", episodes=[], error=f"Timeout after {timeout}s")
    except Exception as exc:
        logger.error("Failed to fetch %s: %s", url, exc)
        return FeedResult(title="", episodes=[], error=f"Failed to fetch: {exc}")

    try:
        parsed = feedparser.parse(raw)
    except Exception as exc:
        logger.error("feedparser crash for %s: %s", url, exc)
        return FeedResult(title="", episodes=[], error=f"Failed to parse feed: {exc}")

    if parsed.bozo and not parsed.entries:
        # bozo exception with zero entries → treat as fatal
        bozo_msg = _bozo_exception_message(parsed.bozo_exception)
        logger.warning("Bozo feed (no entries) at %s: %s", url, bozo_msg)
        return FeedResult(title="", episodes=[], error=bozo_msg)

    feed_title = parsed.feed.get("title", url)
    episodes: list[Episode] = []

    for entry in parsed.entries:
        episode_id = entry.get("id") or entry.get("link", "")
        enclosure_url = _get_enclosure_url(entry) or ""

        episodes.append(
            Episode(
                title=entry.get("title", "(no title)"),
                url=enclosure_url or entry.get("link", ""),
                published=entry.get("published") or entry.get("updated"),
                summary=entry.get("summary"),
                duration=entry.get("itunes_duration"),
                episode_id=episode_id,
            )
        )

    logger.debug("Fetched %d episodes from %s", len(episodes), feed_title)
    return FeedResult(title=feed_title, episodes=episodes,
                      etag=new_etag, last_modified=new_lm)


def _get_enclosure_url(entry: Any) -> str | None:
    """Extract the first audio enclosure URL from a feedparser entry."""
    enclosures = entry.get("enclosures", [])
    for enc in enclosures:
        href = enc.get("href", "")
        mime = (enc.get("type") or "").lower()
        if href and ("audio" in mime or "video" in mime or not mime):
            return href
    return None


def _bozo_exception_message(exception: Any) -> str:
    """Return a human-readable message from a feedparser bozo_exception."""
    if exception is None:
        return "Unknown parsing error"
    msg = str(exception)
    # feedparser wraps some exceptions in its own types
    if hasattr(exception, "getMessage"):
        msg = exception.getMessage()
    return msg or "Unknown parsing error"


# ── async RSS fetching (aiohttp) ───────────────────────────────────

async def fetch_feed_async(url: str, timeout: int = 15,
                           etag: str = "", last_modified: str = "",
                           days_back: int | None = None) -> FeedResult:
    """Async version of :func:`fetch_feed` using ``aiohttp``.

    Behaves identically to the sync version but does not block the
    event loop.  Suitable for use directly with ``await`` in Textual
    screens, avoiding ``asyncio.to_thread`` overhead.

    If *days_back* is set (e.g. 100), only episodes published within
    that many days are returned.  Pass ``None`` (default) for no limit.

    Requires the ``aiohttp`` package (see ``requirements.txt``).
    """
    import aiohttp
    import feedparser  # lazy import — optional dependency

    headers = {"User-Agent": "AetherPod/1.0"}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    new_etag = ""
    new_lm = ""

    try:
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_obj) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 304:
                    logger.debug("Feed unchanged (304): %s", url)
                    return FeedResult(title="", episodes=[], not_modified=True)
                if resp.status >= 400:
                    reason = resp.reason or f"HTTP {resp.status}"
                    logger.error("HTTP %d for %s: %s", resp.status, url, reason)
                    return FeedResult(title="", episodes=[], error=f"HTTP {resp.status}: {reason}")
                raw = await resp.read()
                new_etag = resp.headers.get("ETag", "")
                new_lm = resp.headers.get("Last-Modified", "")
    except asyncio.TimeoutError:
        logger.error("Timeout fetching %s (%ds)", url, timeout)
        return FeedResult(title="", episodes=[], error=f"Timeout after {timeout}s")
    except aiohttp.ClientError as exc:
        logger.error("HTTP client error for %s: %s", url, exc)
        return FeedResult(title="", episodes=[], error=str(exc))
    except Exception as exc:
        logger.error("Failed to fetch %s: %s", url, exc)
        return FeedResult(title="", episodes=[], error=f"Failed to fetch: {exc}")

    try:
        parsed = feedparser.parse(raw)
    except Exception as exc:
        logger.error("feedparser crash for %s: %s", url, exc)
        return FeedResult(title="", episodes=[], error=f"Failed to parse feed: {exc}")

    if parsed.bozo and not parsed.entries:
        bozo_msg = _bozo_exception_message(parsed.bozo_exception)
        logger.warning("Bozo feed (no entries) at %s: %s", url, bozo_msg)
        return FeedResult(title="", episodes=[], error=bozo_msg)

    feed_title = parsed.feed.get("title", url)
    episodes: list[Episode] = []

    for entry in parsed.entries:
        episode_id = entry.get("id") or entry.get("link", "")
        enclosure_url = _get_enclosure_url(entry) or ""

        episodes.append(
            Episode(
                title=entry.get("title", "(no title)"),
                url=enclosure_url or entry.get("link", ""),
                published=entry.get("published") or entry.get("updated"),
                summary=entry.get("summary"),
                duration=entry.get("itunes_duration"),
                episode_id=episode_id,
            )
        )

    # Apply days_back filter (auto-refresh scoping)
    if days_back is not None and days_back > 0:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_back)
        filtered: list[Episode] = []
        for ep in episodes:
            if ep.published:
                pub_dt = _parse_feed_date(ep.published)
                if pub_dt is not None and pub_dt >= cutoff:
                    filtered.append(ep)
                elif pub_dt is None:
                    filtered.append(ep)
            else:
                filtered.append(ep)
        episodes = filtered

    logger.debug("Fetched %d episodes from %s (async)", len(episodes), feed_title)
    return FeedResult(title=feed_title, episodes=episodes,
                      etag=new_etag, last_modified=new_lm)


def _parse_feed_date(raw: str) -> datetime.datetime | None:
    """Parse a feed date string (ISO 8601 or RFC 2822) to a UTC-aware datetime.

    Returns ``None`` if the string cannot be parsed.
    """
    raw = raw.strip()
    parsed: datetime.datetime | None = None
    # Try ISO 8601 first (Atom feeds)
    try:
        parsed = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        pass
    # Try RFC 2822 (RSS feeds)
    if parsed is None:
        try:
            parsed = email_utils.parsedate_to_datetime(raw)
        except (ValueError, TypeError, LookupError):
            pass
    # Ensure timezone-aware; assume UTC if naive
    if parsed is not None and parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed
