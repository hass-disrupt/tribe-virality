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


def bucket_indices_from_mapping(mapping: dict) -> dict[str, np.ndarray]:
    """Parse an ROI-mapping dict into {sub_score: sorted-unique int64 indices}.

    Pure (no file IO). Each bucket carries a ``vertex_indices`` list of
    fsaverage5 vertex ids (atlas-derived, non-contiguous — produced by
    ``data/build_roi_mapping.py``). Indices must lie in ``[0, n_vertices)``
    and each bucket must be non-empty.
    """
    n_vertices = int(mapping["n_vertices"])
    buckets = mapping["buckets"]

    result: dict[str, np.ndarray] = {}
    for name in SUB_SCORE_NAMES:
        if name not in buckets:
            raise KeyError(f"Sub-score {name!r} missing from roi_mapping.json")
        spec = buckets[name]
        if "vertex_indices" not in spec:
            raise ValueError(f"Bucket {name!r} is missing 'vertex_indices'")

        idx = np.unique(np.asarray(spec["vertex_indices"], dtype=np.int64).ravel())
        if idx.size == 0:
            raise ValueError(f"Bucket {name!r} is empty (no vertices)")
        if idx[0] < 0 or idx[-1] >= n_vertices:
            raise ValueError(
                f"Vertex index for {name!r} out of range [0, {n_vertices})"
            )
        result[name] = idx
    return result


@lru_cache(maxsize=1)
def get_bucket_indices() -> Mapping[str, np.ndarray]:
    """Return {sub_score_name: np.ndarray[int] of vertex indices} for each bucket."""
    return bucket_indices_from_mapping(load_roi_mapping())


def expected_n_vertices() -> int:
    return int(load_roi_mapping()["n_vertices"])
