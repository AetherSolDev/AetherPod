# Created: 2026-08-01
# Last Edited: 2026-08-01 03:20 CT (America/Chicago)
# Path: tests/unit/test_eq_presets.py
# Purpose: Unit tests for EQ presets — af-string building and eq.json loading/fallback.

from __future__ import annotations

import json

from aetherpod.eq_presets import (
    DEFAULT_PRESETS,
    _build_af_string,
    _presets_to_map,
    load_eq_presets,
)


class TestBuildAfString:
    def test_off_preset_is_empty(self) -> None:
        assert _build_af_string(DEFAULT_PRESETS[0]) == ""

    def test_full_preset_contains_all_parts(self) -> None:
        af = _build_af_string(DEFAULT_PRESETS[1])
        assert af.startswith("lavfi=[highpass=")
        assert "equalizer=f=" in af
        assert "alimiter=" in af

    def test_highpass_only(self) -> None:
        af = _build_af_string({"highpass": {"frequency": 50}, "eq": [], "limiter": None})
        assert af == "lavfi=[highpass=f=50]"

    def test_eq_only(self) -> None:
        af = _build_af_string(
            {"highpass": None, "eq": [{"frequency": 300, "gain": 2, "q": 1}], "limiter": None}
        )
        assert af == "lavfi=[equalizer=f=300:t=q:w=1:g=2]"

    def test_limiter_only(self) -> None:
        af = _build_af_string(
            {"highpass": None, "eq": [], "limiter": {"level_in": 1.8, "limit": 0.89, "attack": 3, "release": 30}}
        )
        assert af == "alimiter=level_in=1.8:limit=0.89:attack=3:release=30"


class TestLoadEqPresets:
    def test_returns_defaults_when_no_file(self, tmp_path) -> None:
        presets = load_eq_presets(tmp_path)
        assert len(presets) == len(DEFAULT_PRESETS)
        assert presets[0][0] == "Off"

    def test_writes_default_eq_json_on_first_run(self, tmp_path) -> None:
        load_eq_presets(tmp_path)
        assert (tmp_path / "eq.json").is_file()

    def test_loads_custom_file(self, tmp_path) -> None:
        custom = {"presets": [{"label": "Custom", "highpass": None, "eq": [], "limiter": None}]}
        (tmp_path / "eq.json").write_text(json.dumps(custom), encoding="utf-8")
        presets = load_eq_presets(tmp_path)
        assert presets == {0: ("Custom", "")}

    def test_invalid_json_falls_back_to_defaults(self, tmp_path) -> None:
        (tmp_path / "eq.json").write_text("{not valid json", encoding="utf-8")
        presets = load_eq_presets(tmp_path)
        assert presets[0][0] == "Off"

    def test_empty_presets_list_falls_back_to_defaults(self, tmp_path) -> None:
        (tmp_path / "eq.json").write_text(json.dumps({"presets": []}), encoding="utf-8")
        presets = load_eq_presets(tmp_path)
        assert len(presets) == len(DEFAULT_PRESETS)


class TestPresetsToMap:
    def test_labels_and_indices(self) -> None:
        mapped = _presets_to_map(DEFAULT_PRESETS)
        assert [mapped[i][0] for i in range(len(DEFAULT_PRESETS))] == [
            "Off",
            "Bright",
            "Warm",
            "Balanced",
        ]
