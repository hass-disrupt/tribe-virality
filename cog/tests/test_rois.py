"""Tests for the ROI mapping parser (pure, file-independent)."""

from __future__ import annotations

import numpy as np
import pytest

from scoring.constants import SUB_SCORE_NAMES
from scoring.rois import (
    bucket_indices_from_mapping,
    get_bucket_indices,
    load_roi_mapping,
)


def _mapping_with(buckets: dict, n_vertices: int = 20) -> dict:
    return {"n_vertices": n_vertices, "buckets": buckets}


def _all_buckets(**overrides) -> dict:
    """A full 5-bucket mapping; defaults give each a distinct vertex_indices."""
    base = {
        "reward": {"vertex_indices": [0, 1]},
        "emotion": {"vertex_indices": [2, 3]},
        "attention": {"vertex_indices": [4, 5]},
        "novelty": {"vertex_indices": [6, 7]},
        "social_relevance": {"vertex_indices": [8, 9]},
    }
    base.update(overrides)
    return base


def test_vertex_indices_form_returns_sorted_unique_int_array():
    mapping = _mapping_with(_all_buckets(reward={"vertex_indices": [5, 1, 1, 3]}))
    out = bucket_indices_from_mapping(mapping)
    assert out["reward"].dtype == np.int64
    np.testing.assert_array_equal(out["reward"], np.array([1, 3, 5], dtype=np.int64))
    # Every sub-score must be present.
    assert set(out.keys()) == set(SUB_SCORE_NAMES)


def test_out_of_range_vertex_index_raises():
    mapping = _mapping_with(_all_buckets(reward={"vertex_indices": [0, 999]}))
    with pytest.raises(ValueError, match="out of range|range"):
        bucket_indices_from_mapping(mapping)


def test_empty_bucket_raises():
    mapping = _mapping_with(_all_buckets(reward={"vertex_indices": []}))
    with pytest.raises(ValueError, match="empty|no vertices"):
        bucket_indices_from_mapping(mapping)


def test_missing_sub_score_raises():
    buckets = _all_buckets()
    del buckets["novelty"]
    with pytest.raises(KeyError, match="novelty"):
        bucket_indices_from_mapping(_mapping_with(buckets))


def test_shipped_roi_mapping_is_destrieux_atlas():
    """The committed roi_mapping.json is the Destrieux atlas mapping:
    20484 fsaverage5 vertices, every construct populated, disjoint coverage."""
    mapping = load_roi_mapping()
    assert "destrieux" in mapping.get("atlas", "").lower()
    assert mapping["n_vertices"] == 20484
    for name in SUB_SCORE_NAMES:
        spec = mapping["buckets"][name]
        assert "vertex_indices" in spec and len(spec["vertex_indices"]) > 0

    bi = get_bucket_indices()
    seen: set[int] = set()
    for name in SUB_SCORE_NAMES:
        idx = bi[name]
        assert idx.min() >= 0 and idx.max() < 20484
        s = set(int(v) for v in idx)
        assert not (s & seen), f"{name} overlaps another construct"
        seen |= s
