"""ROI bucket loader. Produces per-bucket vertex index arrays."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Mapping

import numpy as np

from .constants import SUB_SCORE_NAMES


@lru_cache(maxsize=1)
def load_roi_mapping() -> dict:
    """Load the ROI mapping JSON from cog/data/."""
    here = Path(__file__).resolve().parent.parent  # cog/
    with (here / "data" / "roi_mapping.json").open("r") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def get_bucket_indices() -> Mapping[str, np.ndarray]:
    """Return {sub_score_name: np.ndarray[int] of vertex indices} for each bucket."""
    mapping = load_roi_mapping()
    n_vertices = int(mapping["n_vertices"])
    buckets = mapping["buckets"]

    result: dict[str, np.ndarray] = {}
    for name in SUB_SCORE_NAMES:
        if name not in buckets:
            raise KeyError(f"Sub-score {name!r} missing from roi_mapping.json")
        ranges = buckets[name]["vertex_ranges"]
        parts = []
        for start, stop in ranges:
            if not (0 <= start < stop <= n_vertices):
                raise ValueError(f"Invalid vertex range [{start}, {stop}) for {name!r}")
            parts.append(np.arange(start, stop, dtype=np.int64))
        result[name] = np.concatenate(parts) if parts else np.empty(0, dtype=np.int64)
    return result


def expected_n_vertices() -> int:
    return int(load_roi_mapping()["n_vertices"])
