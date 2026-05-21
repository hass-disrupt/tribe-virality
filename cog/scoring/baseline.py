"""Baseline statistics loader."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .constants import SUB_SCORE_NAMES


def parse_baseline_stats(raw: dict) -> dict[str, dict[str, float]]:
    """Parse a baseline-stats dict into ``{sub_score: {mean, std}}``.

    Pure (no file IO). Tolerates top-level ``_comment``/``provenance`` and any
    extra per-entry keys (e.g. the empirical format's ``n_videos``).
    """
    out: dict[str, dict[str, float]] = {}
    for name in SUB_SCORE_NAMES:
        if name not in raw:
            raise KeyError(f"Sub-score {name!r} missing from baseline_stats.json")
        entry = raw[name]
        out[name] = {"mean": float(entry["mean"]), "std": float(entry["std"])}
        if out[name]["std"] <= 0:
            raise ValueError(f"Baseline std for {name!r} must be > 0")
    return out


@lru_cache(maxsize=1)
def load_baseline_stats() -> dict[str, dict[str, float]]:
    """Return {sub_score: {"mean": float, "std": float}} from the baked JSON."""
    here = Path(__file__).resolve().parent.parent  # cog/
    with (here / "data" / "baseline_stats.json").open("r") as f:
        raw = json.load(f)
    return parse_baseline_stats(raw)
