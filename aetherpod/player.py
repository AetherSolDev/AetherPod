# Created: 2026-07-19
# Last Edited: 2026-07-27 16:09 CT (America/Chicago)
# Path: aetherpod/player.py
# Purpose: High-level Player wrapping an AudioEngine — queue, cache, progress callbacks.

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

from platformdirs import user_cache_dir

from aetherpod.engines import (
    AudioEngine,
    MpvEngine,
    PlayerStatus,
    detect_engine,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, float, float], None]
"""``callback(episode_id, position_seconds, total_length_seconds)``"""


class Player:
    """High-level media player wrapping an :class:`AudioEngine`.

    Manages play queue, download cache, and progress callbacks.
    Auto-detects the best available engine (mpv > VLC > ffplay) unless
    an engine is explicitly provided.
    """

    def __init__(self, engine: AudioEngine | None = None) -> None:
        self._engine = engine or detect_engine()
        if self._engine is None:
            raise RuntimeError(
                "No audio engine found. Install mpv, VLC, or ffplay."
            )
        logger.info("Player using engine: %s", self._engine.name)

        self._lock = threading.Lock()
        self._current_episode_id: str = ""
        self._current_episode_url: str = ""
        self._current_feed_url: str = ""
        self._paused: bool = False
        self._generation: int = 0
        self._stopped_by_user: bool = False
        self._progress_callback: ProgressCallback | None = None
        self._cache_dir = Path(user_cache_dir("aetherpod", ensure_exists=True))
        self._temp_files: list[Path] = []

        # Play queue: (url, episode_id, title) tuples
        self._queue: list[tuple[str, str, str]] = []

    # ── public API ───────────────────────────────────────────────────

    def play(self, url: str, episode_id: str = "",
             progress_callback: ProgressCallback | None = None,
             start_pos: float | None = None) -> str | None:
        """Start playing *url*.

        If *start_pos* is provided (and > 0), resumes from that position.

        Returns ``None`` on success, or an error message string on failure.
        """
        with self._lock:
            if self._engine.is_playing():
                return "Already playing — stop first"

            self._stopped_by_user = False
            self._progress_callback = progress_callback
            self._current_episode_id = episode_id
            self._current_episode_url = url
            self._paused = False
            self._generation += 1
            gen = self._generation

        err = self._engine.play(url, start_pos)
        if err:
            return err

        # Spawn wait loop in a daemon thread
        threading.Thread(
            target=self._wait_loop,
            args=(episode_id, progress_callback, gen),
            daemon=True,
        ).start()
        return None

    def stop(self) -> None:
        """Stop playback immediately."""
        with self._lock:
            self._stopped_by_user = True
        self._engine.stop()
        with self._lock:
            self._current_episode_id = ""
            self._current_episode_url = ""

    def is_playing(self) -> bool:
        """Return ``True`` if the engine is currently playing."""
        return self._engine.is_playing()

    def is_process_alive(self) -> bool:
        """Return ``True`` if the engine subprocess is running, without side effects."""
        return self._engine.is_playing()

    def toggle_pause(self) -> bool | None:
        """Toggle play/pause. Returns new paused state or ``None``."""
        result = self._engine.toggle_pause()
        if result is not None:
            self._paused = result
        return result

    def seek(self, offset: float = 30.0) -> None:
        """Seek forward (+) or backward (-) by *offset* seconds."""
        self._engine.seek(offset)

    def seek_absolute(self, position: float) -> None:
        """Seek to an absolute *position* in seconds."""
        self._engine.seek_absolute(position)

    def get_status(self) -> PlayerStatus | None:
        """Query engine for current playback status."""
        return self._engine.get_status()

    def get_current_episode_id(self) -> str:
        """Return the episode_id of the currently (or last) played episode."""
        with self._lock:
            return self._current_episode_id

    def get_current_episode_url(self) -> str:
        """Return the audio URL of the currently (or last) played episode."""
        with self._lock:
            return self._current_episode_url

    def set_current_feed_url(self, feed_url: str) -> None:
        """Store the feed URL of the currently playing episode."""
        with self._lock:
            self._current_feed_url = feed_url

    def get_current_feed_url(self) -> str:
        """Return the feed URL of the currently playing episode."""
        with self._lock:
            return self._current_feed_url

    def get_live_progress(self) -> tuple[float, float]:
        """Return the latest (position, duration) from the engine."""
        return self._engine.get_live_progress()

    # ── speed control ─────────────────────────────────────────────────

    SPEEDS = MpvEngine.SPEEDS

    def set_speed(self, speed: float) -> None:
        """Set playback speed."""
        self._engine.set_speed(speed)

    def get_speed(self) -> float:
        """Return current playback speed."""
        return self._engine.get_speed()

    # ── play queue ───────────────────────────────────────────────────

    def add_to_queue(self, url: str, episode_id: str, title: str) -> None:
        """Append an episode to the play queue."""
        with self._lock:
            self._queue.append((url, episode_id, title))

    def remove_from_queue(self, index: int) -> None:
        """Remove an episode from the play queue by index."""
        with self._lock:
            if 0 <= index < len(self._queue):
                self._queue.pop(index)

    def clear_queue(self) -> None:
        """Clear all queued episodes."""
        with self._lock:
            self._queue.clear()

    def get_queue(self) -> list[tuple[str, str, str]]:
        """Return a copy of the play queue."""
        with self._lock:
            return list(self._queue)

    @property
    def queue_count(self) -> int:
        """Number of items in the play queue."""
        with self._lock:
            return len(self._queue)

    def _play_next(self) -> None:
        """Start the next queued episode, if any."""
        with self._lock:
            if not self._queue or self._engine.is_playing():
                return
            url, episode_id, title = self._queue.pop(0)
        logger.info("Queue auto-play: %s", title)
        err = self.play(url, episode_id, self._progress_callback)
        if err:
            logger.error("Queue auto-play failed: %s", err)

    # ── cache ────────────────────────────────────────────────────────

    def cleanup_cache(self) -> None:
        """Remove all temp download files from this session."""
        for p in self._temp_files:
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
        self._temp_files.clear()

    def cache_path_for(self, episode_id: str) -> Path:
        """Return the expected cache path for a given episode ID."""
        return self._cache_dir / f"{episode_id}.mp3"

    # ── internal: wait loop ──────────────────────────────────────────

    def _wait_loop(self, episode_id: str, callback: ProgressCallback | None,
                   gen: int) -> None:
        """Wait for engine playback to finish, then report progress.

        Reads engine stdout for live progress updates, waits for the
        subprocess to exit, and calls the progress callback with the
        final position.
        """
        last_pos = 0.0
        last_len = 0.0

        # Poll stdout during playback (best-effort, engine-dependent)
        while self._engine.is_playing():
            self._engine.read_stdout()
            live_pos, live_len = self._engine.get_live_progress()
            if live_pos > 0:
                last_pos = live_pos
                last_len = live_len
            # Sleep between polling cycles
            try:
                import time
                time.sleep(0.5)
            except KeyboardInterrupt:
                break

        # Wait for process to fully exit
        rc = self._engine.wait_for_exit()
        logger.debug("_wait_loop: engine exited with code %s (final pos=%.1f/%.1f)",
                     rc, last_pos, last_len)

        with self._lock:
            active = self._generation == gen

        if callback and last_pos > 0 and active:
            try:
                callback(episode_id, last_pos, last_len)
            except Exception as exc:
                logger.warning("Progress callback failed: %s", exc)

        with self._lock:
            if active and self._current_episode_id:
                self._current_episode_id = ""
                self._current_episode_url = ""

        if active and not self._stopped_by_user:
            self._play_next()
