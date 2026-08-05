# Created: 2026-08-01
# Last Edited: 2026-08-05 15:29 CT (America/Chicago)
# Path: tests/unit/test_engines.py
# Purpose: Unit tests for audio-engine binary discovery (Windows install dirs, registry, platform gating).

from __future__ import annotations

from pathlib import Path

import pytest

import aetherpod.engines as eng


class TestFindBinary:
    def test_path_lookup_first(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(eng.shutil, "which", lambda name: f"/usr/bin/{name}")
        assert eng._find_binary("mpv") == "/usr/bin/mpv"

    def test_none_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(eng.shutil, "which", lambda name: None)
        monkeypatch.setattr(eng.os, "name", "posix")
        assert eng._find_binary("nonexistent-tool") is None


class TestFindWindowsInstallDir:
    def test_skipped_off_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(eng.os, "name", "posix")
        assert eng._find_windows_install_dir("vlc.exe") is None

    def test_finds_vlc_in_program_files(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        vlc_dir = tmp_path / "Program Files" / "VideoLAN" / "VLC"
        vlc_dir.mkdir(parents=True)
        vlc_dir.joinpath("vlc.exe").write_bytes(b"MZ")
        monkeypatch.setattr(eng.os, "name", "nt")
        monkeypatch.setenv("ProgramFiles", str(tmp_path / "Program Files"))
        monkeypatch.delenv("ProgramFiles(x86)", raising=False)
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.delenv("USERPROFILE", raising=False)
        found = eng._find_windows_install_dir("vlc.exe")
        assert found is not None
        assert found.endswith("vlc.exe")

    def test_none_when_not_installed(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(eng.os, "name", "nt")
        monkeypatch.setenv("ProgramFiles", str(tmp_path))
        monkeypatch.delenv("ProgramFiles(x86)", raising=False)
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.delenv("USERPROFILE", raising=False)
        assert eng._find_windows_install_dir("vlc.exe") is None


class TestFindMacosInstallDir:
    def test_skipped_off_macos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(eng.os, "name", "posix")
        monkeypatch.setattr(eng.sys, "platform", "linux")
        assert eng._find_macos_install_dir("vlc") is None

    def test_skipped_on_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(eng.os, "name", "nt")
        monkeypatch.setattr(eng.sys, "platform", "win32")
        assert eng._find_macos_install_dir("vlc") is None

    def test_finds_vlc_app_bundle(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(eng.os, "name", "posix")
        monkeypatch.setattr(eng.sys, "platform", "darwin")
        monkeypatch.setattr(eng.os, "sep", "/")
        posixpath = __import__("posixpath")
        expected = "/Applications/VLC.app/Contents/MacOS/vlc"
        monkeypatch.setattr(eng.os, "path", posixpath)
        monkeypatch.setattr(posixpath, "isfile", lambda p: p == expected)
        found = eng._find_macos_install_dir("vlc")
        assert found is not None
        assert found.endswith("VLC.app/Contents/MacOS/vlc")

    def test_none_when_not_installed(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(eng.os, "name", "posix")
        monkeypatch.setattr(eng.sys, "platform", "darwin")
        monkeypatch.setattr(eng.os, "sep", "/")
        posixpath = __import__("posixpath")
        monkeypatch.setattr(posixpath, "expanduser", lambda p: str(tmp_path))
        monkeypatch.setattr(eng.os, "path", posixpath)
        assert eng._find_macos_install_dir("vlc") is None


class TestVlcRegistryPath:
    def test_none_off_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(eng.os, "name", "posix")
        assert eng._vlc_registry_path() is None


class TestEngineAvailability:
    def test_mpv_unavailable_on_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """mpv uses AF_UNIX IPC (Linux/macOS only) — must be skipped on Windows."""
        monkeypatch.setattr(eng.os, "name", "nt")
        assert eng.MpvEngine.available() is False

    def test_mpv_available_on_posix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(eng.os, "name", "posix")
        monkeypatch.setattr(eng, "_find_binary", lambda name: "/usr/bin/mpv")
        assert eng.MpvEngine.available() is True

    def test_vlc_available_via_install_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(eng.os, "name", "nt")
        monkeypatch.setattr(eng, "_find_binary", lambda name: "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe")
        assert eng.VlcEngine.available() is True

    def test_vlc_available_via_registry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(eng, "_find_binary", lambda name: None)
        monkeypatch.setattr(eng, "_vlc_registry_path", lambda: "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe")
        assert eng.VlcEngine.available() is True


class TestDetectEngineWindows:
    def test_prefers_vlc_over_mpv_on_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On Windows, mpv is skipped (AF_UNIX) so VLC must be selected."""
        monkeypatch.setattr(eng.os, "name", "nt")
        monkeypatch.setattr(eng, "_find_binary", lambda name: "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe")
        monkeypatch.setattr(eng, "_vlc_registry_path", lambda: None)
        engine = eng.detect_engine()
        assert engine is not None
        assert isinstance(engine, eng.VlcEngine)


class TestDetectEngineMacos:
    def test_prefers_mpv_when_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On macOS mpv works (AF_UNIX is supported) and should win over VLC."""
        monkeypatch.setattr(eng.os, "name", "posix")
        monkeypatch.setattr(eng, "_find_binary", lambda name: f"/opt/homebrew/bin/{name}")
        monkeypatch.setattr(eng, "_vlc_registry_path", lambda: None)
        engine = eng.detect_engine()
        assert engine is not None
        assert isinstance(engine, eng.MpvEngine)

    def test_falls_back_to_vlc_app_bundle(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If mpv is missing but VLC.app exists, macOS should use VLC."""
        monkeypatch.setattr(eng.os, "name", "posix")
        monkeypatch.setattr(eng.sys, "platform", "darwin")
        monkeypatch.setattr(eng, "_find_binary", lambda name: (
            None if name == "mpv"
            else "/Applications/VLC.app/Contents/MacOS/vlc"
        ))
        monkeypatch.setattr(eng, "_vlc_registry_path", lambda: None)
        engine = eng.detect_engine()
        assert engine is not None
        assert isinstance(engine, eng.VlcEngine)


class TestMpvResumeArg:
    def test_start_uses_equals_form(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """mpv rejects `--start value` (space) — it must be `--start=value`.

        Regression: AetherPod downloaded the episode for resume but mpv exited
        immediately with "Error parsing commandline option start: option requires
        parameter", so playback silently restarted from 0.
        """
        captured: list[list[str]] = []

        class FakePopen:
            def __init__(self, cmd, **kwargs):
                captured.append(cmd)
                self.stdout = None
                self.stderr = None

            def poll(self):
                return None

        monkeypatch.setattr(eng.subprocess, "Popen", FakePopen)
        monkeypatch.setattr(eng, "_find_binary", lambda name: "/usr/bin/mpv")

        engine = eng.MpvEngine()
        engine.play("https://example.com/ep.mp3", start_pos=123.4)

        assert captured, "mpv was never launched"
        cmd = captured[0]
        start_flags = [a for a in cmd if a.startswith("--start")]
        assert start_flags == ["--start=123.4"], f"bad start flag: {start_flags}"

    def test_no_start_flag_without_position(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[list[str]] = []

        class FakePopen:
            def __init__(self, cmd, **kwargs):
                captured.append(cmd)
                self.stdout = None
                self.stderr = None

            def poll(self):
                return None

        monkeypatch.setattr(eng.subprocess, "Popen", FakePopen)
        monkeypatch.setattr(eng, "_find_binary", lambda name: "/usr/bin/mpv")

        engine = eng.MpvEngine()
        engine.play("https://example.com/ep.mp3")  # no start_pos

        assert not any(a.startswith("--start") for a in captured[0])
