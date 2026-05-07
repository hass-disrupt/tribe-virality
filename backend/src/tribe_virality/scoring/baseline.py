"""Baseline statistics loader."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources

from .constants import SUB_SCORE_NAMES


@lru_cache(maxsize=1)
def load_baseline_stats() -> dict[str, dict[str, float]]:
    """Return {sub_score: {"mean": float, "std": float}}."""
    with resources.files("tribe_virality.data").joinpath("baseline_stats.json").open("r") as f:
        raw = json.load(f)
    out: dict[str, dict[str, float]] = {}
    for name in SUB_SCORE_NAMES:
        if name not in raw:
            raise KeyError(f"Sub-score {name!r} missing from baseline_stats.json")
        entry = raw[name]
        out[name] = {"mean": float(entry["mean"]), "std": float(entry["std"])}
        if out[name]["std"] <= 0:
            raise ValueError(f"Baseline std for {name!r} must be > 0")
    return out
