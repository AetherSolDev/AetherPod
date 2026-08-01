# Created: 2026-07-28
# Last Edited: 2026-07-28 17:13 CT (America/Chicago)
# Path: aetherpod/eq_presets.py
# Purpose: Load/build EQ preset strings from eq.json, with hardcoded defaults.

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PRESETS: list[dict[str, Any]] = [
    {
        "label": "Off",
        "highpass": None,
        "eq": [],
        "limiter": None,
    },
    {
        "label": "Bright",
        "highpass": {"frequency": 100},
        "eq": [
            {"frequency": 200, "gain": -2, "q": 1},
            {"frequency": 300, "gain": 2, "q": 1},
            {"frequency": 2500, "gain": 3.5, "q": 1.5},
            {"frequency": 5000, "gain": 1.5, "q": 1},
        ],
        "limiter": {"level_in": 1.8, "limit": 0.89, "attack": 3, "release": 30},
    },
    {
        "label": "Warm",
        "highpass": {"frequency": 50},
        "eq": [
            {"frequency": 100, "gain": 4, "q": 1},
            {"frequency": 500, "gain": 2, "q": 1},
            {"frequency": 3000, "gain": 2.5, "q": 1.5},
            {"frequency": 7000, "gain": -2, "q": 1},
        ],
        "limiter": {"level_in": 1.8, "limit": 0.89, "attack": 3, "release": 30},
    },
    {
        "label": "Balanced",
        "highpass": {"frequency": 80},
        "eq": [
            {"frequency": 200, "gain": 1.5, "q": 1},
            {"frequency": 300, "gain": 1.5, "q": 1},
            {"frequency": 2500, "gain": 3, "q": 1.5},
            {"frequency": 6000, "gain": -1, "q": 1},
        ],
        "limiter": {"level_in": 1.5, "limit": 0.89, "attack": 5, "release": 50},
    },
]


def _build_af_string(preset: dict[str, Any]) -> str:
    parts: list[str] = []

    hp = preset.get("highpass")
    if hp:
        parts.append(f"highpass=f={hp['frequency']}")

    for band in preset.get("eq", []):
        f = band["frequency"]
        g = band["gain"]
        q = band.get("q", 1)
        parts.append(f"equalizer=f={f}:t=q:w={q}:g={g}")

    lavfi = ""
    if parts:
        lavfi = f"lavfi=[{','.join(parts)}]"

    lim = preset.get("limiter")
    alim = ""
    if lim:
        alim = (f"alimiter=level_in={lim['level_in']}:limit={lim['limit']}"
                f":attack={lim['attack']}:release={lim['release']}")

    return ",".join(filter(None, [lavfi, alim]))


def _presets_to_map(presets: list[dict[str, Any]]) -> dict[int, tuple[str, str]]:
    return {
        i: (p["label"], _build_af_string(p))
        for i, p in enumerate(presets)
    }


def load_eq_presets(config_dir: str | Path) -> dict[int, tuple[str, str]]:
    path = Path(config_dir) / "eq.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw = data.get("presets", [])
            if not raw or not isinstance(raw, list):
                raise ValueError("presets must be a non-empty list")
            return _presets_to_map(raw)
        except Exception as exc:
            logger.warning("Failed to load eq.json: %s — using defaults", exc)
    else:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_defaults(path)
        except OSError as exc:
            logger.warning("Could not write default eq.json: %s", exc)
    return _presets_to_map(DEFAULT_PRESETS)


def _write_defaults(path: Path) -> None:
    doc = {
        "_readme": (
            "AetherPod EQ presets.  Edit freely — invalid values fall back to built-in defaults."
            "  highpass: {frequency} or null.  eq: [{frequency, gain (dB), q}...].  "
            "limiter: {level_in, limit, attack (ms), release (ms)} or null."
        ),
        "presets": DEFAULT_PRESETS,
    }
    text = json.dumps(doc, indent=2, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")
    logger.info("Wrote default eq.json to %s", path)
