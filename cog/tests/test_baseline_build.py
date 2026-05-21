"""Tests for the pure pieces of the baseline-stats generator."""

from __future__ import annotations

import numpy as np
import pytest

from scoring.baseline_build import compute_baseline_stats
from scoring.constants import SUB_SCORE_NAMES
from scoring.pipeline import roi_mean_activations
from scoring.rois import expected_n_vertices


def test_roi_mean_activations_constant_preds():
    """Constant preds -> every construct's mean activation equals the fill."""
    v = expected_n_vertices()
    preds = np.full((6, v), 0.37, dtype=np.float64)
    means = roi_mean_activations(preds)
    assert set(means) == set(SUB_SCORE_NAMES)
    for name in SUB_SCORE_NAMES:
        assert means[name] == pytest.approx(0.37)


def test_roi_mean_activations_matches_pipeline_subscore_input():
    """The mean activation must equal preds[:, idx].mean() for that bucket."""
    from scoring.rois import get_bucket_indices

    v = expected_n_vertices()
    rng = np.random.default_rng(0)
    preds = rng.normal(size=(4, v))
    means = roi_mean_activations(preds)
    bi = get_bucket_indices()
    for name in SUB_SCORE_NAMES:
        assert means[name] == pytest.approx(float(preds[:, bi[name]].mean()))


def test_compute_baseline_stats_mean_and_std_across_videos():
    per_video = {
        "reward": [0.1, 0.3, 0.2],
        "emotion": [1.0, 1.2, 0.8, 1.0],
        "attention": [0.0, 0.4],
        "novelty": [0.5, 0.7, 0.9],
        "social_relevance": [-0.2, 0.2],
    }
    stats = compute_baseline_stats(per_video)
    assert stats["reward"]["mean"] == pytest.approx(0.2)
    assert stats["reward"]["std"] == pytest.approx(np.std([0.1, 0.3, 0.2]))
    # Provenance must record how many reference videos contributed.
    assert stats["reward"]["n_videos"] == 3


def test_compute_baseline_stats_rejects_too_few_videos():
    with pytest.raises(ValueError, match="at least 2|videos"):
        compute_baseline_stats({n: [0.5] for n in SUB_SCORE_NAMES})


def test_compute_baseline_stats_rejects_zero_variance():
    with pytest.raises(ValueError, match="std|variance|constant"):
        compute_baseline_stats({n: [0.5, 0.5, 0.5] for n in SUB_SCORE_NAMES})


def test_compute_baseline_stats_requires_every_sub_score():
    incomplete = {n: [0.1, 0.2] for n in SUB_SCORE_NAMES if n != "novelty"}
    with pytest.raises(KeyError, match="novelty"):
        compute_baseline_stats(incomplete)


def test_parse_baseline_stats_ignores_provenance_and_empirical_n_videos():
    """The pure parser must ignore top-level _comment/provenance and the
    per-entry n_videos that the empirical format adds."""
    from scoring.baseline import parse_baseline_stats

    raw = {
        "_comment": "x",
        "provenance": "empirical",
        **{n: {"mean": 0.1, "std": 0.2, "n_videos": 30} for n in SUB_SCORE_NAMES},
    }
    stats = parse_baseline_stats(raw)
    for n in SUB_SCORE_NAMES:
        assert stats[n] == {"mean": 0.1, "std": 0.2}


def test_parse_baseline_stats_validates():
    from scoring.baseline import parse_baseline_stats

    with pytest.raises(KeyError, match="emotion"):
        parse_baseline_stats({n: {"mean": 0, "std": 1} for n in SUB_SCORE_NAMES
                              if n != "emotion"})
    with pytest.raises(ValueError, match="std"):
        parse_baseline_stats({n: {"mean": 0, "std": 0} for n in SUB_SCORE_NAMES})


def test_shipped_baseline_stats_file_loads():
    """The committed (relabeled) baseline_stats.json still loads cleanly."""
    from scoring.baseline import load_baseline_stats

    load_baseline_stats.cache_clear()
    stats = load_baseline_stats()
    for n in SUB_SCORE_NAMES:
        assert stats[n]["std"] > 0
