"""Tests for the pure Destrieux -> construct mapping builder."""

from __future__ import annotations

import numpy as np
import pytest

from scoring.atlas import (
    DESTRIEUX_CONSTRUCT_PARCELS,
    build_roi_mapping_dict,
)
from scoring.constants import SUB_SCORE_NAMES


def test_build_maps_named_parcels_to_constructs_with_rh_offset():
    # 4 labels; lh has 3 vertices, rh has 3 vertices -> 6 total.
    label_names = ["Unknown", "G_reward_x", "G_emo_x", "G_other"]
    labels_lh = np.array([0, 1, 2], dtype=np.int64)  # v0->Unknown,v1->reward,v2->emo
    labels_rh = np.array([1, 3, 2], dtype=np.int64)  # v3->reward,v4->other,v5->emo
    construct_parcels = {
        "reward": ["G_reward"],
        "emotion": ["G_emo"],
        "attention": ["G_other"],
        "novelty": ["G_other"],
        "social_relevance": ["G_other"],
    }
    out = build_roi_mapping_dict(
        label_names, labels_lh, labels_rh, construct_parcels
    )
    assert out["n_vertices"] == 6
    # reward parcel = label idx 1 -> lh vertex 1 and rh vertex (3 + 0) = 3
    assert out["buckets"]["reward"]["vertex_indices"] == [1, 3]
    # emotion parcel = label idx 2 -> lh vertex 2 and rh vertex (3 + 2) = 5
    assert out["buckets"]["emotion"]["vertex_indices"] == [2, 5]
    # substring match, not exact: "G_other" matched by prefix "G_other"
    assert out["buckets"]["attention"]["vertex_indices"] == [4]


def test_substring_match_is_used_for_parcel_names():
    label_names = ["Unknown", "G_orbital_lateral", "G_rectus", "G_filler"]
    labels_lh = np.array([1, 2], dtype=np.int64)  # orbital_lateral, rectus
    labels_rh = np.array([3, 3], dtype=np.int64)  # filler -> keeps others non-empty
    cp = {
        "reward": ["G_orbital", "G_rectus"],  # fragments, not exact names
        "emotion": ["G_filler"],
        "attention": ["G_filler"],
        "novelty": ["G_filler"],
        "social_relevance": ["G_filler"],
    }
    out = build_roi_mapping_dict(label_names, labels_lh, labels_rh, cp)
    # both lh vertices match a reward parcel by substring; rh (filler) does not
    assert out["buckets"]["reward"]["vertex_indices"] == [0, 1]


def test_construct_with_no_matching_vertices_raises():
    label_names = ["Unknown", "G_a"]
    labels_lh = np.array([0, 1], dtype=np.int64)
    labels_rh = np.array([0, 1], dtype=np.int64)
    cp = {n: ["G_a"] for n in SUB_SCORE_NAMES}
    cp["novelty"] = ["DOES_NOT_EXIST"]
    with pytest.raises(ValueError, match="novelty"):
        build_roi_mapping_dict(label_names, labels_lh, labels_rh, cp)


def test_default_destrieux_table_covers_all_constructs_with_real_parcel_names():
    # The shipped table must define every sub-score and use plausible
    # Destrieux (aparc.a2009s) parcel-name fragments (no empties).
    assert set(DESTRIEUX_CONSTRUCT_PARCELS) == set(SUB_SCORE_NAMES)
    for name, parcels in DESTRIEUX_CONSTRUCT_PARCELS.items():
        assert parcels, f"{name} has no parcels"
        assert all(isinstance(p, str) and p for p in parcels)
    # A few anchor parcels we expect to be present per the methodology.
    assert any("orbital" in p.lower() for p in DESTRIEUX_CONSTRUCT_PARCELS["reward"])
    assert any("insul" in p.lower() for p in DESTRIEUX_CONSTRUCT_PARCELS["emotion"])
    assert any(
        "calcarine" in p.lower() or "occipital" in p.lower()
        for p in DESTRIEUX_CONSTRUCT_PARCELS["attention"]
    )
    assert any(
        "parahip" in p.lower() or "Post" in p
        for p in DESTRIEUX_CONSTRUCT_PARCELS["novelty"]
    )
    assert any(
        "precuneus" in p.lower() or "Angular" in p
        for p in DESTRIEUX_CONSTRUCT_PARCELS["social_relevance"]
    )
