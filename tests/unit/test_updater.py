# Created: 2026-08-01
# Last Edited: 2026-08-01 11:41 CT (America/Chicago)
# Path: tests/unit/test_updater.py
# Purpose: Unit tests for the version-comparison logic in aetherpod/updater.

from __future__ import annotations

from aetherpod.updater import UpdateCheck, _version_tuple, is_newer_than


class TestVersionTuple:
    def test_plain(self) -> None:
        assert _version_tuple("0.4.3") == (0, 4, 3)

    def test_leading_v(self) -> None:
        assert _version_tuple("v0.4.3") == (0, 4, 3)

    def test_short_versions_padded(self) -> None:
        assert _version_tuple("0.4") == (0, 4, 0)

    def test_prerelease_suffix_ignored(self) -> None:
        assert _version_tuple("0.4.3-rc1") == (0, 4, 3)

    def test_non_numeric_segment_zeroed(self) -> None:
        assert _version_tuple("0.x.3") == (0, 0, 3)


class TestIsNewerThan:
    def test_newer(self) -> None:
        assert is_newer_than("0.4.3", "0.4.2")

    def test_same(self) -> None:
        assert not is_newer_than("0.4.3", "0.4.3")

    def test_older(self) -> None:
        assert not is_newer_than("0.4.2", "0.4.3")

    def test_patch_bump(self) -> None:
        assert is_newer_than("0.4.10", "0.4.9")

    def test_major_bump(self) -> None:
        assert is_newer_than("1.0.0", "0.9.9")

    def test_with_v_prefix(self) -> None:
        assert is_newer_than("v0.4.3", "0.4.2")


class TestUpdateCheck:
    def test_available_message(self) -> None:
        check = UpdateCheck(available=True, latest="0.4.3", current="0.4.2")
        assert "Update available" in check.message
        assert "aetherpod -u" in check.message

    def test_up_to_date_message(self) -> None:
        check = UpdateCheck(available=False, current="0.4.3")
        assert "latest version" in check.message
