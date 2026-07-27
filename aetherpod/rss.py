# Created: 2026-07-27
# Last Edited: 2026-07-27 15:54 CT (America/Chicago)
# Path: aetherpod/rss.py
# Purpose: RSS/Atom feed fetching and parsing — fetch_feed, fetch_feed_async, helpers.

from __future__ import annotations

import asyncio
import datetime
import logging
import urllib.error
import urllib.request
from email import utils as email_utils
from typing import Any

from aetherpod.models import Episode, FeedResult

logger = logging.getLogger(__name__)

REFRESH_DAYS = 100
"""Default number of days of episodes to show on auto-refresh."""


def fetch_feed(url: str, timeout: int = 15,
              etag: str = "", last_modified: str = "") -> FeedResult:
    """Parse an RSS/Atom feed and return structured episode data."""
    import feedparser  # lazy import — optional dependency

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
    if hasattr(exception, "getMessage"):
        msg = exception.getMessage()
    return msg or "Unknown parsing error"


async def fetch_feed_async(url: str, timeout: int = 15,
                           etag: str = "", last_modified: str = "",
                           days_back: int | None = None) -> FeedResult:
    """Async version of :func:`fetch_feed` using ``aiohttp``."""
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
    """Parse a feed date string (ISO 8601 or RFC 2822) to a UTC-aware datetime."""
    if not raw:
        return None
    raw = raw.strip()
    parsed: datetime.datetime | None = None
    try:
        parsed = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        pass
    if parsed is None:
        try:
            parsed = email_utils.parsedate_to_datetime(raw)
        except (ValueError, TypeError, LookupError):
            pass
    if parsed is not None and parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed
