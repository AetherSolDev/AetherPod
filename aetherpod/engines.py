# Created: 2026-07-26
# Last Edited: 2026-08-05 15:29 CT (America/Chicago)
# Path: aetherpod/engines.py
# Purpose: Audio engine abstraction — MpvEngine, VlcEngine, FfplayEngine.

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

logger = logging.getLogger(__name__)

# ── Binary discovery ──────────────────────────────────────────────────

_WINDOWS_INSTALL_DIRS: dict[str, list[tuple[str, ...]]] = {
    # exe name → relative paths under Program Files / Program Files (x86) / LOCALAPPDATA
    "vlc.exe": [
        ("VideoLAN", "VLC", "vlc.exe"),
    ],
    "mpv.exe": [
        ("mpv", "mpv.exe"),
    ],
    "ffplay.exe": [
        ("ffmpeg", "bin", "ffplay.exe"),
    ],
}


def _find_windows_install_dir(exe: str) -> str | None:
    """Search common Windows install locations for *exe* (not on PATH by default).

    VLC, mpv, and ffmpeg are typically installed under ``Program Files``
    without being added to PATH, so ``shutil.which`` misses them.
    """
    if os.name != "nt":
        return None
    rel_paths = _WINDOWS_INSTALL_DIRS.get(exe.lower())
    if not rel_paths:
        return None
    roots = []
    for var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        val = os.environ.get(var)
        if val:
            roots.append(val)
    user = os.environ.get("USERPROFILE", "")
    for root in roots:
        for rel in rel_paths:
            candidate = os.path.join(root, *rel)
            if os.path.isfile(candidate):
                return candidate
    if user:
        for rel in rel_paths:
            candidate = os.path.join(user, "scoop", "apps", rel[-2], "current", rel[-1])
            if os.path.isfile(candidate):
                return candidate
    return None


_MACOS_INSTALL_PATHS: dict[str, list[tuple[str, ...]]] = {
    # binary name → candidate absolute paths (relative to home dir)
    "vlc": [
        ("Applications", "VLC.app", "Contents", "MacOS", "vlc"),
        ("Applications", "VLC.app", "Contents", "MacOS", "VLC"),
    ],
    "mpv": [
        ("opt", "homebrew", "bin", "mpv"),       # Apple Silicon
        ("usr", "local", "bin", "mpv"),          # Intel / older Homebrew
    ],
    "ffplay": [
        ("opt", "homebrew", "bin", "ffplay"),
        ("usr", "local", "bin", "ffplay"),
    ],
}


def _find_macos_install_dir(name: str) -> str | None:
    """Search common macOS install locations for *name* (not on PATH by default).

    VLC.app is a bundle under ``/Applications`` and is never on PATH; Homebrew
    (``/opt/homebrew`` on Apple Silicon, ``/usr/local`` on Intel) may also be
    missing from PATH in non-interactive shells.
    """
    if os.name != "posix" or sys.platform != "darwin":
        return None
    for rel in _MACOS_INSTALL_PATHS.get(name, ()):
        candidate = os.path.join(os.sep, *rel)
        if os.path.isfile(candidate):
            return candidate
    home = os.path.expanduser("~")
    for rel in _MACOS_INSTALL_PATHS.get(name, ()):
        candidate = os.path.join(home, *rel)
        if os.path.isfile(candidate):
            return candidate
    return None


def _find_binary(name: str) -> str | None:
    """Locate an executable by PATH, then by common platform install dirs.

    On Windows, VLC/ffmpeg live under ``Program Files``; on macOS, VLC.app and
    Homebrew may not be on PATH.  ``shutil.which`` alone misses all of these.
    """
    found = shutil.which(name)
    if found:
        return found
    exe = name if name.lower().endswith(".exe") else name + ".exe"
    win = _find_windows_install_dir(exe)
    if win:
        return win
    return _find_macos_install_dir(name)


def _vlc_registry_path() -> str | None:
    """Return VLC's install path from the Windows registry, if present."""
    if os.name != "nt":
        return None
    try:
        import winreg  # Windows only
    except ImportError:
        return None
    for hive, key_path in (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\VideoLAN\VLC"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\VideoLAN\VLC"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\VideoLAN\VLC"),
    ):
        try:
            with winreg.OpenKey(hive, key_path) as key:
                install_dir, _ = winreg.QueryValueEx(key, "InstallDir")
            if install_dir and os.path.isfile(os.path.join(install_dir, "vlc.exe")):
                return os.path.join(install_dir, "vlc.exe")
        except (OSError, TypeError):
            continue
    return None


@dataclass
class PlayerStatus:
    """Snapshot of current playback state."""
    is_playing: bool = False
    is_paused: bool = False
    position: float = 0.0
    duration: float = 0.0


# ── Abstract base ─────────────────────────────────────────────────────


class AudioEngine(ABC):
    """Abstract interface for a media-player subprocess engine."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable engine name (e.g. 'mpv', 'VLC', 'ffplay')."""

    @classmethod
    @abstractmethod
    def available(cls) -> bool:
        """Return True if the required binary is found in PATH."""

    @abstractmethod
    def play(self, url: str, start_pos: float | None = None) -> str | None:
        """Start playback of *url*. Return None on success, error string on failure."""

    @abstractmethod
    def stop(self) -> None:
        """Terminate playback immediately."""

    @abstractmethod
    def toggle_pause(self) -> bool | None:
        """Toggle pause. Return new paused state (True=paused), or None if unavailable."""

    @abstractmethod
    def seek(self, offset: float) -> None:
        """Seek relative by *offset* seconds (+/-)."""

    @abstractmethod
    def seek_absolute(self, position: float) -> None:
        """Seek to absolute *position* in seconds."""

    @abstractmethod
    def get_status(self) -> PlayerStatus | None:
        """Return current status, or None if not available."""

    @abstractmethod
    def is_playing(self) -> bool:
        """Return True if the subprocess is currently running."""

    @abstractmethod
    def set_speed(self, speed: float) -> None:
        """Set playback speed."""

    @abstractmethod
    def get_speed(self) -> float:
        """Return current playback speed."""

    @abstractmethod
    def get_live_progress(self) -> tuple[float, float]:
        """Return latest (position, duration) from engine's output."""

    @abstractmethod
    def wait_for_exit(self, timeout: float | None = None) -> int | None:
        """Wait for process to exit and return returncode, or None if not started."""

    @abstractmethod
    def set_eq(self, af_string: str) -> None:
        """Set active audio filter chain (lavfi + native). Empty string clears filters."""

    @abstractmethod
    def cleanup(self) -> None:
        """Clean up temp files, sockets, etc."""


# ── MpvEngine ─────────────────────────────────────────────────────────


class MpvEngine(AudioEngine):
    """Engine wrapping an mpv subprocess with Unix-socket JSON IPC.

    IPC is AF_UNIX (Linux/macOS only); on Windows the mpv engine is
    skipped in favor of VLC (AF_INET), which works on all platforms.
    """

    BINARY: ClassVar[str] = "mpv"
    SPEEDS: ClassVar[list[float]] = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
    _POS_RE: ClassVar[re.Pattern] = re.compile(r"POS=([\d.]+)\s+LEN=([\d.]+)")

    def __init__(self) -> None:
        self._proc: subprocess.Popen[bytes] | None = None
        self._socket_path: str | None = None
        self._sock: socket.socket | None = None
        self._speed: float = 1.0
        self._live_position: float = 0.0
        self._live_duration: float = 0.0
        self._available: bool | None = None

    # ── AudioEngine ────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "mpv"

    @classmethod
    def available(cls) -> bool:
        if os.name == "nt":
            return False  # AF_UNIX IPC unsupported on Windows → use VLC
        return _find_binary(cls.BINARY) is not None

    def play(self, url: str, start_pos: float | None = None) -> str | None:
        self.stop()
        try:
            sock_dir = tempfile.mkdtemp(prefix="aetherpod-mpv-")
            self._socket_path = os.path.join(sock_dir, "mpv.sock")
        except OSError as exc:
            logger.error("Failed to create IPC socket dir: %s", exc)
            return f"Failed to create IPC socket: {exc}"

        binary = _find_binary(self.BINARY) or self.BINARY
        cmd = [
            binary,
            "--no-video",
            "--audio-display=no",
            f"--input-ipc-server={self._socket_path}",
            "--term-status-msg=POS=${=time-pos} LEN=${=duration}",
            "--user-agent=AetherPod/1.0",
        ]
        if start_pos is not None and start_pos > 0:
            # mpv requires `--start=value` — the space-separated form
            # ("--start value") is rejected for numeric options and mpv
            # exits immediately with code 1.
            cmd.append(f"--start={start_pos}")
        cmd.append(url)

        logger.debug("mpv command: %s", " ".join(cmd))
        try:
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

        return None

    def stop(self) -> None:
        proc = self._proc
        if proc is None:
            return
        logger.debug("Stopping mpv (pid %d)", proc.pid)
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        self._proc = None
        self._close_ipc()
        self._cleanup_socket()

    def toggle_pause(self) -> bool | None:
        resp = self._ipc_command({"command": ["cycle", "pause"]})
        if resp and resp.get("error") == "success":
            return resp.get("data", False)
        return None

    def seek(self, offset: float) -> None:
        self._ipc_command({"command": ["seek", offset, "relative"]})

    def seek_absolute(self, position: float) -> None:
        self._ipc_command({"command": ["seek", position, "absolute"]})

    def get_status(self) -> PlayerStatus | None:
        if not self.is_playing():
            return None
        try:
            pause_resp = self._ipc_command({"command": ["get_property", "pause"]})
            pos_resp = self._ipc_command({"command": ["get_property", "time-pos"]})
            dur_resp = self._ipc_command({"command": ["get_property", "duration"]})
        except Exception:
            return None
        if pause_resp is None:
            return None
        return PlayerStatus(
            is_playing=True,
            is_paused=bool(pause_resp.get("data", False)),
            position=float(pos_resp.get("data", 0) if pos_resp else 0),
            duration=float(dur_resp.get("data", 0) if dur_resp else 0),
        )

    def is_playing(self) -> bool:
        proc = self._proc
        if proc is None:
            return False
        ret = proc.poll()
        if ret is not None:
            self._proc = None
            self._close_ipc()
            self._cleanup_socket()
            return False
        return True

    def set_speed(self, speed: float) -> None:
        self._speed = speed
        self._ipc_command({"command": ["set_property", "speed", speed]})

    def get_speed(self) -> float:
        return self._speed

    def get_live_progress(self) -> tuple[float, float]:
        return self._live_position, self._live_duration

    def wait_for_exit(self, timeout: float | None = None) -> int | None:
        proc = self._proc
        if proc is None:
            return None
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None
        rc = proc.returncode
        self._proc = None
        self._close_ipc()
        self._cleanup_socket()
        return rc

    def set_eq(self, af_string: str) -> None:
        for attempt in range(5):
            resp = self._ipc_command({"command": ["set_property", "af", af_string]})
            if resp is not None:
                break
            time.sleep(0.2)

    def cleanup(self) -> None:
        self._close_ipc()
        self._cleanup_socket()

    # ── internal ─────────────────────────────────────────────────────

    def _connect_ipc(self) -> bool:
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
        except OSError as exc:
            logger.debug("IPC connect failed: %s", exc)
            self._sock = None
            return False

    def _ipc_command(self, cmd: dict) -> dict | None:
        if self._sock is None:
            if not self._connect_ipc():
                return None
        try:
            payload = json.dumps(cmd) + "\n"
            self._sock.sendall(payload.encode("utf-8"))
            raw = self._sock.recv(4096)
            if raw:
                text = raw.decode("utf-8").strip()
                for line in text.split("\n"):
                    line = line.strip()
                    if line:
                        try:
                            return json.loads(line)
                        except json.JSONDecodeError:
                            continue
        except OSError as exc:
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

    def read_stdout(self) -> list[str]:
        """Read available lines from mpv stdout and parse POS/LEN."""
        proc = self._proc
        if proc is None or proc.stdout is None:
            return []
        lines = []
        try:
            chunk = proc.stdout.read(4096)
            if not chunk:
                return []
            buf = chunk
            while True:
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
                            self._live_position = float(m.group(1))
                            self._live_duration = float(m.group(2))
                        except ValueError:
                            pass
                    else:
                        lines.append(line)
            return lines
        except Exception:
            return []


# ── VlcEngine ─────────────────────────────────────────────────────────


class VlcEngine(AudioEngine):
    """Engine wrapping a VLC subprocess with RC (remote control) interface via TCP.

    Uses VLC's ``--intf rc`` to send commands over a local TCP socket.
    Provides full play/pause/seek/speed control.
    Works on Linux, macOS, and Windows.
    """

    BINARY: ClassVar[str] = "vlc"
    _RC_PORT: ClassVar[int] = 4212
    _RC_HOST: ClassVar[str] = "127.0.0.1"
    SPEEDS: ClassVar[list[float]] = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]

    def __init__(self) -> None:
        self._proc: subprocess.Popen[bytes] | None = None
        self._sock: socket.socket | None = None
        self._speed: float = 1.0
        self._paused: bool = False
        self._live_position: float = 0.0
        self._live_duration: float = 0.0

    # ── AudioEngine ────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "VLC"

    @classmethod
    def available(cls) -> bool:
        if _find_binary(cls.BINARY) is not None:
            return True
        return _vlc_registry_path() is not None

    def play(self, url: str, start_pos: float | None = None) -> str | None:
        self.stop()
        binary = _find_binary(self.BINARY) or self.BINARY
        cmd = [
            binary,
            "--intf", "rc",
            f"--rc-host={self._RC_HOST}:{self._RC_PORT}",
            "--no-video",
            "--play-and-exit",
        ]
        if start_pos is not None and start_pos > 0:
            cmd.extend(["--start-time", str(start_pos)])
        cmd.append(url)

        logger.debug("VLC command: %s", " ".join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self._proc = None
            logger.error("Failed to start VLC: %s", exc)
            return f"Failed to start VLC: {exc}"

        time.sleep(0.3)
        return None

    def stop(self) -> None:
        self._rc_command("stop")
        self._rc_command("shutdown")
        self._close_rc()
        proc = self._proc
        if proc is not None:
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            self._proc = None

    def toggle_pause(self) -> bool | None:
        self._rc_command("pause")
        self._paused = not self._paused
        return self._paused

    def seek(self, offset: float) -> None:
        if offset >= 0:
            self._rc_command(f"seek +{offset}")
        else:
            self._rc_command(f"seek {offset}")

    def seek_absolute(self, position: float) -> None:
        self._rc_command(f"seek {position}")

    def get_status(self) -> PlayerStatus | None:
        if not self.is_playing():
            return None
        time_resp = self._rc_command("get_time")
        len_resp = self._rc_command("get_length")
        pos = 0.0
        dur = 0.0
        if time_resp:
            try:
                pos = float(time_resp.strip())
            except ValueError:
                pass
        if len_resp:
            try:
                dur = float(len_resp.strip())
            except ValueError:
                pass
        return PlayerStatus(
            is_playing=True,
            is_paused=self._paused,
            position=pos,
            duration=dur,
        )

    def is_playing(self) -> bool:
        proc = self._proc
        if proc is None:
            return False
        ret = proc.poll()
        if ret is not None:
            self._proc = None
            self._close_rc()
            return False
        return True

    def set_speed(self, speed: float) -> None:
        self._speed = speed
        self._rc_command(f"rate {speed}")

    def get_speed(self) -> float:
        return self._speed

    def get_live_progress(self) -> tuple[float, float]:
        return self._live_position, self._live_duration

    def wait_for_exit(self, timeout: float | None = None) -> int | None:
        proc = self._proc
        if proc is None:
            return None
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None
        rc = proc.returncode
        self._proc = None
        self._close_rc()
        return rc

    def set_eq(self, af_string: str) -> None:
        pass  # VLC does not support lavfi-style audio filter chains

    def cleanup(self) -> None:
        self._close_rc()

    # ── internal: RC interface ─────────────────────────────────────

    def _connect_rc(self) -> bool:
        if self._sock is not None:
            return True
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((self._RC_HOST, self._RC_PORT))
            self._sock = s
            return True
        except OSError as exc:
            logger.debug("VLC RC connect failed: %s", exc)
            self._sock = None
            return False

    def _rc_command(self, cmd: str) -> str | None:
        if self._sock is None:
            if not self._connect_rc():
                return None
        try:
            self._sock.sendall((cmd + "\n").encode("utf-8"))
            time.sleep(0.05)
            raw = self._sock.recv(4096)
            if raw:
                text = raw.decode("utf-8", errors="replace").strip()
                lines = [l for l in text.split("\n") if l.strip()]
                return lines[-1] if lines else None
        except OSError as exc:
            logger.debug("VLC RC command failed: %s", exc)
            self._sock = None
        return None

    def _close_rc(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception as exc:
                logger.debug("VLC RC close: %s", exc)
            self._sock = None


# ── FfplayEngine ──────────────────────────────────────────────────────


class FfplayEngine(AudioEngine):
    """Minimal engine wrapping an ffplay subprocess.

    Provides basic play/stop and pause via stdin commands.
    No seek, no speed control, no progress reporting.
    Falls back to this when mpv and VLC are both unavailable.
    """

    BINARY: ClassVar[str] = "ffplay"

    def __init__(self) -> None:
        self._proc: subprocess.Popen[bytes] | None = None
        self._speed: float = 1.0

    # ── AudioEngine ────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "ffplay"

    @classmethod
    def available(cls) -> bool:
        return _find_binary(cls.BINARY) is not None

    def play(self, url: str, start_pos: float | None = None) -> str | None:
        self.stop()
        binary = _find_binary(self.BINARY) or self.BINARY
        cmd = [
            binary,
            "-nodisp",
            "-autoexit",
            "-loglevel", "quiet",
        ]
        if start_pos is not None and start_pos > 0:
            cmd.extend(["-ss", str(start_pos)])
        cmd.append(url)

        logger.debug("ffplay command: %s", " ".join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self._proc = None
            logger.error("Failed to start ffplay: %s", exc)
            return f"Failed to start ffplay: {exc}"
        return None

    def stop(self) -> None:
        proc = self._proc
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except OSError:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        self._proc = None

    def toggle_pause(self) -> bool | None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            return None
        try:
            proc.stdin.write(b"p\n")
            proc.stdin.flush()
        except OSError:
            return None
        return None

    def seek(self, offset: float) -> None:
        pass

    def seek_absolute(self, position: float) -> None:
        pass

    def get_status(self) -> PlayerStatus | None:
        if not self.is_playing():
            return None
        return PlayerStatus(is_playing=True)

    def is_playing(self) -> bool:
        proc = self._proc
        if proc is None:
            return False
        ret = proc.poll()
        if ret is not None:
            self._proc = None
            return False
        return True

    def set_speed(self, speed: float) -> None:
        self._speed = speed

    def get_speed(self) -> float:
        return self._speed

    def get_live_progress(self) -> tuple[float, float]:
        return (0.0, 0.0)

    def wait_for_exit(self, timeout: float | None = None) -> int | None:
        proc = self._proc
        if proc is None:
            return None
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None
        rc = proc.returncode
        self._proc = None
        return rc

    def set_eq(self, af_string: str) -> None:
        pass  # ffplay does not support runtime af changes

    def cleanup(self) -> None:
        pass


# ── Factory ────────────────────────────────────────────────────────────

_ENGINE_CLASSES: list[type[AudioEngine]] = [
    MpvEngine,
    VlcEngine,
    FfplayEngine,
]


def detect_engine() -> AudioEngine | None:
    """Return the best available audio engine by checking PATH order: mpv > VLC > ffplay."""
    for cls in _ENGINE_CLASSES:
        logger.debug("Checking engine: %s", cls.__name__)
        try:
            if cls.available():
                engine = cls()
                logger.info("Using audio engine: %s", engine.name)
                return engine
        except Exception as exc:
            logger.warning("Engine check failed for %s: %s", cls.__name__, exc)
    logger.warning("No audio engine found (mpv, VLC, or ffplay required)")
    return None
