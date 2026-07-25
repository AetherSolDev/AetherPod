# Created: 2026-07-19
# Last Edited: 2026-07-25 17:01 CT (America/Chicago)
# Path: src/player.py
# Purpose: MpvPlayer — non-blocking subprocess wrapper for mpv with IPC control.

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from platformdirs import user_cache_dir

logger = logging.getLogger(__name__)

_MPV_BIN = "mpv"

ProgressCallback = Callable[[str, float, float], None]
"""``callback(episode_id, position_seconds, total_length_seconds)``"""


@dataclass
class PlayerStatus:
    """Snapshot of current mpv playback state."""

    is_playing: bool = False
    is_paused: bool = False
    position: float = 0.0
    duration: float = 0.0


class MpvPlayer:
    """Manages an mpv subprocess for audio stream playback.

    Runs mpv in a daemon thread so the TUI stays responsive. Provides
    play/stop/pause/seek/status operations via a Unix-socket JSON IPC
    channel (``--input-ipc-server``).
    """

    def __init__(self) -> None:
        self._proc: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()
        self._available: bool | None = None  # lazily checked
        self._socket_path: str | None = None
        self._sock: socket.socket | None = None
        self._current_episode_id: str = ""
        self._current_episode_url: str = ""
        self._current_feed_url: str = ""
        self._paused: bool = False
        # Live position/duration updated from mpv stdout every ~1s during playback
        self._live_position: float = 0.0
        self._live_duration: float = 0.0
        # Generation counter: incremented on each play() so stale _wait_loop
        # threads from a previous play() don't clean up the NEW instance's
        # socket/temp-directory resources.
        self._generation: int = 0
        self._speed: float = 1.0
        # Play queue: (url, episode_id, title) tuples
        self._queue: list[tuple[str, str, str]] = []
        self._stopped_by_user: bool = False
        self._progress_callback: ProgressCallback | None = None
        # Download cache for reliable resume
        self._cache_dir = Path(user_cache_dir("aetherpod", ensure_exists=True))
        self._temp_files: list[Path] = []

    # ── public API ───────────────────────────────────────────────────

    def play(self, url: str, episode_id: str = "",
             progress_callback: ProgressCallback | None = None,
             start_pos: float | None = None) -> str | None:
        """Start playing *url* in a background thread with an IPC socket.

        When mpv exits, *progress_callback* is invoked with
        ``(episode_id, position, total_length)`` so the caller can
        persist playback position via :meth:`DataManager.save_progress`.

        If *start_pos* is provided (and > 0), mpv starts at that
        position (used for resume from saved progress).

        Returns ``None`` on success, or an error message string on failure.
        """
        if not self._check_available():
            return "mpv is not installed or not in PATH"

        with self._lock:
            if self._proc is not None:
                return "Already playing — stop first"

            self._stopped_by_user = False
            self._progress_callback = progress_callback

            # Create a temp directory + socket for IPC
            try:
                sock_dir = tempfile.mkdtemp(prefix="aetherpod-mpv-")
                self._socket_path = os.path.join(sock_dir, "mpv.sock")
                logger.debug("IPC socket dir created: %s", sock_dir)
                logger.debug("IPC socket path: %s", self._socket_path)
            except OSError as exc:
                logger.error("Failed to create IPC socket dir: %s", exc)
                return f"Failed to create IPC socket: {exc}"

            logger.info("Starting mpv: %s (start=%s)", url, start_pos)
            try:
                cmd = [
                    _MPV_BIN,
                    "--no-video",
                    "--audio-display=no",
                    f"--input-ipc-server={self._socket_path}",
                    "--term-status-msg=POS=${=time-pos} LEN=${=duration}",
                    "--user-agent=AetherPod/1.0",
                ]
                if start_pos is not None and start_pos > 0:
                    cmd.extend(["--start", str(start_pos)])
                cmd.append(url)
                logger.debug("mpv subprocess command: %s", " ".join(cmd))
                self._proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                self._proc = None
                self._cleanup_socket()
                logger.error("Failed to start mpv: %s", exc)
                return f"Failed to start mpv: {exc}"

            self._current_episode_id = episode_id
            self._current_episode_url = url
            self._paused = False
            self._generation += 1
            gen = self._generation

        # Wait for mpv to finish in a daemon thread
        threading.Thread(
            target=self._wait_loop,
            args=(episode_id, progress_callback, gen),
            daemon=True,
        ).start()
        return None

    def stop(self) -> None:
        """Kill the current mpv process if running.

        Sets ``self._proc = None`` so a subsequent :meth:`play` call
        doesn't see a stale ``Popen`` object and reject with
        "Already playing — stop first".
        """
        with self._lock:
            proc = self._proc
            self._stopped_by_user = True
        if proc is None:
            return
        logger.debug("Stopping mpv (pid %d)", proc.pid)
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        with self._lock:
            if self._proc is proc:
                self._proc = None
                self._current_episode_id = ""
        self._close_ipc()
        self._cleanup_socket()

    def is_playing(self) -> bool:
        """Return ``True`` if mpv is currently running."""
        with self._lock:
            proc = self._proc
        if proc is None:
            return False
        ret = proc.poll()
        if ret is not None:
            with self._lock:
                if self._proc is proc:
                    self._proc = None
            self._close_ipc()
            self._cleanup_socket()
            return False
        return True

    def is_process_alive(self) -> bool:
        """Return ``True`` if the mpv subprocess is running, without side effects.

        Unlike :meth:`is_playing`, this does **not** set ``_proc = None``
        or clean up the IPC socket when the process has exited.  Use this
        when you only need to check liveness without mutating internal state
        (e.g. during the 1s poll interval where a concurrent ``_wait_loop``
        thread may already be handling cleanup).
        """
        with self._lock:
            proc = self._proc
        if proc is None:
            return False
        return proc.poll() is None

    # ── IPC control ──────────────────────────────────────────────────

    def toggle_pause(self) -> bool | None:
        """Toggle play/pause via IPC.

        Returns the new paused state (``True`` = paused), or ``None``
        if IPC is not available.
        """
        resp = self._ipc_command({"command": ["cycle", "pause"]})
        if resp and resp.get("error") == "success":
            self._paused = not self._paused
            return self._paused
        return None

    def seek(self, offset: float = 30.0) -> None:
        """Seek forward (+) or backward (-) by *offset* seconds."""
        self._ipc_command({"command": ["seek", offset, "relative"]})

    def seek_absolute(self, position: float) -> None:
        """Seek to an absolute *position* in seconds."""
        self._ipc_command({"command": ["seek", position, "absolute"]})

    def get_status(self) -> PlayerStatus | None:
        """Query mpv for current playback status, or ``None`` if not connected."""
        if not self.is_playing():
            return None
        # Query multiple properties
        try:
            pause_resp = self._ipc_command({"command": ["get_property", "pause"]})
            pos_resp = self._ipc_command({"command": ["get_property", "time-pos"]})
            dur_resp = self._ipc_command({"command": ["get_property", "duration"]})
        except Exception:
            return None

        if pause_resp is None:
            return None

        paused = bool(pause_resp.get("data", False))
        self._paused = paused
        return PlayerStatus(
            is_playing=True,
            is_paused=paused,
            position=float(pos_resp.get("data", 0) if pos_resp else 0),
            duration=float(dur_resp.get("data", 0) if dur_resp else 0),
        )

    def get_current_episode_id(self) -> str:
        """Return the episode_id of the currently (or last) played episode."""
        with self._lock:
            return self._current_episode_id

    def get_current_episode_url(self) -> str:
        """Return the audio URL of the currently (or last) played episode.

        Used as a fallback identifier in ``_refresh_playing_item`` when
        the episode has no RSS GUID (empty ``episode_id``).
        """
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
        """Return the latest (position, duration) from mpv stdout during playback.

        Unlike :meth:`get_status` (which queries the IPC socket), this returns
        values parsed directly from mpv's ``--term-status-msg`` output, so it
        works even when the IPC socket is not yet connected.
        Thread-safe.
        """
        with self._lock:
            return (self._live_position, self._live_duration)

    # ── speed control ─────────────────────────────────────────────────

    SPEEDS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    """Available playback speed steps, cycled by ``[`` / ``]`` keys."""

    def set_speed(self, speed: float) -> None:
        """Set playback speed via mpv ``set_property speed`` IPC command.

        Args:
            speed: Playback rate (0.5 = half speed, 2.0 = double).
        """
        self._speed = speed
        self._ipc_command({"command": ["set_property", "speed", speed]})

    def get_speed(self) -> float:
        """Return the current playback speed."""
        return self._speed

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
            if not self._queue or self._proc is not None:
                return
            url, episode_id, title = self._queue.pop(0)
        logger.info("Queue auto-play: %s", title)
        err = self.play(url, episode_id, self._progress_callback)
        if err:
            logger.error("Queue auto-play failed: %s", err)

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

    # ── internal: IPC ────────────────────────────────────────────────

    def _connect_ipc(self) -> bool:
        """Connect (or reconnect) to the mpv IPC Unix socket."""
        if self._sock is not None:
            return True
        path = self._socket_path
        if not path or not os.path.exists(path):
            return False
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(path)
            self._sock = s
            return True
        except (OSError, socket.error) as exc:
            logger.debug("IPC connect failed: %s", exc)
            self._sock = None
            return False

    def _ipc_command(self, cmd: dict) -> dict | None:
        """Send a JSON command to mpv and return the parsed response."""
        if self._sock is None:
            if not self._connect_ipc():
                return None
        try:
            payload = json.dumps(cmd) + "\n"
            self._sock.sendall(payload.encode("utf-8"))
            # mpv sends one JSON line per command
            raw = self._sock.recv(4096)
            if raw:
                return json.loads(raw.decode("utf-8").strip())
        except (OSError, socket.error, json.JSONDecodeError) as exc:
            logger.debug("IPC command failed: %s", exc)
            self._sock = None
        return None

    def _close_ipc(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception as exc:
                logger.debug("IPC close: %s", exc)
            self._sock = None

    def _cleanup_socket(self) -> None:
        if self._socket_path:
            sock_dir = os.path.dirname(self._socket_path)
            try:
                if os.path.exists(self._socket_path):
                    os.unlink(self._socket_path)
                if os.path.isdir(sock_dir):
                    os.rmdir(sock_dir)
            except OSError as exc:
                logger.debug("Socket cleanup: %s", exc)
            self._socket_path = None

    # ── internal: process lifecycle ──────────────────────────────────

    _POS_RE = re.compile(r"POS=([\d.]+)\s+LEN=([\d.]+)")

    def _check_available(self) -> bool:
        """Return ``True`` if ``mpv`` is found in PATH (cached)."""
        if self._available is not None:
            return self._available
        import shutil
        self._available = shutil.which(_MPV_BIN) is not None
        return self._available

    def _wait_loop(self, episode_id: str, callback: ProgressCallback | None,
                   gen: int) -> None:
        """Wait for mpv to exit, then report final playback position.

        Reads mpv stdout byte-by-byte and splits on ``\\r`` **or** ``\\n``
        because mpv's ``--term-status-msg`` uses ``\\r`` (carriage return)
        to overwrite the same terminal line.  Without this, the status
        messages would never be parsed and :attr:`_live_position` /
        :attr:`_live_duration` would stay ``0.0`` during playback.

        *gen* is the generation captured at spawn time.  If a newer
        :meth:`play` call has already taken over (``self._generation != gen``),
        this thread skips all resource cleanup to avoid deleting the new
        instance's socket / temp directory.
        """
        with self._lock:
            proc = self._proc
        if proc is None:
            return

        last_pos = 0.0
        last_len = 0.0
        buf = b""
        lines_parsed = 0

        try:
            assert proc.stdout is not None
            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                buf += chunk
                while True:
                    # Find earliest \r or \n
                    idx = -1
                    for sep in (b"\r", b"\n"):
                        pos = buf.find(sep)
                        if pos != -1 and (idx == -1 or pos < idx):
                            idx = pos
                    if idx == -1:
                        break
                    line = buf[:idx].decode("utf-8", errors="replace").strip()
                    buf = buf[idx + 1:]
                    if line:
                        m = self._POS_RE.search(line)
                        if m:
                            try:
                                last_pos = float(m.group(1))
                                last_len = float(m.group(2))
                                with self._lock:
                                    self._live_position = last_pos
                                    self._live_duration = last_len
                                lines_parsed += 1
                                if lines_parsed == 1:
                                    logger.debug("_wait_loop: first POS=%.1f LEN=%.1f",
                                                 last_pos, last_len)
                            except ValueError:
                                pass
                        else:
                            logger.debug("_wait_loop: mpv stdout: %r", line)
        except Exception:
            pass

        logger.debug("_wait_loop: mpv ended — %d line(s) parsed, final pos=%.1f/%.1f",
                     lines_parsed, last_pos, last_len)

        try:
            proc.wait()
        except Exception as exc:
            logger.warning("_wait_loop proc.wait: %s", exc)

        # Only clean up resources if we're still the active generation — a newer
        # play() call may have already started with its own socket/temp dir.
        # Clear _proc first so a new play() can start, but keep
        # _current_episode_id until after the callback so the UI can still
        # identify the just-played episode during repopulate.
        with self._lock:
            if self._generation == gen and self._proc is proc:
                self._proc = None
            active = self._generation == gen

        if active:
            self._close_ipc()
            self._cleanup_socket()

        if callback and last_pos > 0:
            try:
                callback(episode_id, last_pos, last_len)
            except Exception as exc:
                logger.warning("Progress callback failed: %s", exc)

        # Clear episode id after the callback so _build_row_cells can still
        # show the "playing" indicator during the final repopulate.
        with self._lock:
            if self._generation == gen and self._current_episode_id:
                self._current_episode_id = ""

        logger.info("_wait_loop: mpv exited with code %s after %d line(s) (pos=%.1f/%.1f)",
                     proc.returncode, lines_parsed, last_pos, last_len)

        # If mpv ended naturally (not stopped by user) and queue has items, play next
        if active and not self._stopped_by_user:
            self._play_next()
