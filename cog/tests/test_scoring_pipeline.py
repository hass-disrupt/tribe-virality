"""Tests for the pure scoring pipeline."""

from __future__ import annotations

import numpy as np
import pytest

from scoring.constants import SUB_SCORE_NAMES, WEIGHTS
from scoring.pipeline import score_preds
from scoring.rois import expected_n_vertices


def _make_preds(t: int, fill: float = 0.5) -> np.ndarray:
    v = expected_n_vertices()
    return np.full((t, v), fill, dtype=np.float64)


def test_neutral_input_lands_at_50():
    """A constant array at the baseline mean should score 50 on every sub-score."""
    preds = _make_preds(t=10, fill=0.50)
    result = score_preds(preds, video_duration_s=5.0)
    for name in SUB_SCORE_NAMES:
        # sigmoid(0) = 0.5 -> 50
        assert abs(result.sub_scores[name] - 50.0) < 0.01
    assert result.headline_score == 50


def test_high_activation_pushes_score_up():
    """Activation above baseline mean should yield scores > 50."""
    preds = _make_preds(t=5, fill=0.8)
    result = score_preds(preds, video_duration_s=2.0)
    for name in SUB_SCORE_NAMES:
        assert result.sub_scores[name] > 50
    assert result.headline_score > 50


def test_low_activation_pushes_score_down():
    preds = _make_preds(t=5, fill=0.2)
    result = score_preds(preds, video_duration_s=2.0)
    for name in SUB_SCORE_NAMES:
        assert result.sub_scores[name] < 50
    assert result.headline_score < 50


def test_timeline_length_matches_timesteps():
    preds = _make_preds(t=7, fill=0.5)
    result = score_preds(preds, video_duration_s=3.5)
    assert len(result.timeline) == 7
    # First and last times span the duration.
    assert result.timeline[0]["t"] == pytest.approx(0.0)
    assert result.timeline[-1]["t"] == pytest.approx(3.5)


def test_timeline_rows_contain_all_sub_scores_and_t():
    preds = _make_preds(t=3, fill=0.5)
    result = score_preds(preds, video_duration_s=1.5)
    expected_keys = {"t", *SUB_SCORE_NAMES}
    for row in result.timeline:
        assert set(row.keys()) == expected_keys
        for name in SUB_SCORE_NAMES:
            assert 0.0 <= row[name] <= 100.0


def test_headline_uses_declared_weights():
    """Construct preds where each sub-score has a distinct mean activation,
    then verify the headline equals the weighted combination."""
    from scoring.rois import get_bucket_indices
    v = expected_n_vertices()
    preds = np.zeros((5, v), dtype=np.float64)
    # Give each bucket a different value; keep on baseline mean 0.5 for others not needed (all buckets covered).
    values = {
        "reward": 0.7,
        "emotion": 0.6,
        "attention": 0.55,
        "novelty": 0.45,
        "social_relevance": 0.5,
    }
    for name, val in values.items():
        preds[:, get_bucket_indices()[name]] = val

    result = score_preds(preds, video_duration_s=1.0)
    expected_headline = sum(WEIGHTS[name] * result.sub_scores[name] for name in SUB_SCORE_NAMES)
    assert result.headline_score == int(round(expected_headline))


def test_deterministic_across_calls():
    preds = _make_preds(t=4, fill=0.6)
    r1 = score_preds(preds, video_duration_s=2.0)
    r2 = score_preds(preds, video_duration_s=2.0)
    assert r1 == r2


def test_wrong_vertex_count_raises():
    bad = np.zeros((3, 10), dtype=np.float64)
    with pytest.raises(ValueError, match="vertices"):
        score_preds(bad, video_duration_s=1.0)


def test_bad_duration_raises():
    preds = _make_preds(t=3, fill=0.5)
    with pytest.raises(ValueError, match="duration"):
        score_preds(preds, video_duration_s=0.0)


def test_bad_preds_shape_raises():
    with pytest.raises(ValueError, match="2D"):
        score_preds(np.zeros(10, dtype=np.float64), video_duration_s=1.0)
