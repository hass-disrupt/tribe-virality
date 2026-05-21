"""Tests for the pure scoring pipeline."""

from __future__ import annotations

import numpy as np
import pytest

from scoring.baseline import load_baseline_stats
from scoring.constants import ROI_SIGN, SUB_SCORE_NAMES, WEIGHTS
from scoring.pipeline import score_preds
from scoring.rois import expected_n_vertices, get_bucket_indices


def _make_preds(t: int, fill: float = 0.5) -> np.ndarray:
    v = expected_n_vertices()
    return np.full((t, v), fill, dtype=np.float64)


def _make_preds_at_offset(t: int, offset_sigmas: float) -> np.ndarray:
    """Fill each construct's ROI vertices so its activation sits exactly
    `offset_sigmas` standard deviations from *that construct's* baseline mean.

    This makes the scoring z-score equal to `offset_sigmas` for every construct
    regardless of the shipped baseline_stats.json values, so the tests verify
    the scoring math rather than any particular calibration.
    """
    v = expected_n_vertices()
    preds = np.zeros((t, v), dtype=np.float64)
    baseline = load_baseline_stats()
    bi = get_bucket_indices()
    for name in SUB_SCORE_NAMES:
        mu = baseline[name]["mean"]
        sigma = baseline[name]["std"]
        preds[:, bi[name]] = mu + offset_sigmas * sigma
    return preds


def test_neutral_input_lands_at_50():
    """Activation exactly at each construct's baseline mean → z=0 → 50, and a
    headline of 50."""
    preds = _make_preds_at_offset(t=10, offset_sigmas=0.0)
    result = score_preds(preds, video_duration_s=5.0)
    for name in SUB_SCORE_NAMES:
        # sigmoid(0) = 0.5 -> 50
        assert abs(result.sub_scores[name] - 50.0) < 0.01
    assert result.headline_score == 50


def test_activation_above_baseline_moves_each_sub_score_in_its_signed_direction():
    """One sigma above each construct's baseline moves the sub-score in the
    direction of its ROI_SIGN: positive-sign constructs rise above 50, the
    sign-inverted `emotion` falls below 50."""
    preds = _make_preds_at_offset(t=5, offset_sigmas=+1.0)
    result = score_preds(preds, video_duration_s=2.0)
    for name in SUB_SCORE_NAMES:
        if ROI_SIGN[name] > 0:
            assert result.sub_scores[name] > 50
        else:
            assert result.sub_scores[name] < 50


def test_activation_below_baseline_moves_each_sub_score_in_its_signed_direction():
    """Mirror image: one sigma below baseline, positive-sign constructs fall
    below 50 and the sign-inverted `emotion` rises above 50."""
    preds = _make_preds_at_offset(t=5, offset_sigmas=-1.0)
    result = score_preds(preds, video_duration_s=2.0)
    for name in SUB_SCORE_NAMES:
        if ROI_SIGN[name] > 0:
            assert result.sub_scores[name] < 50
        else:
            assert result.sub_scores[name] > 50


def test_emotion_sign_is_inverted_relative_to_reward():
    """Per Genevsky & Knutson (PNAS 2020), higher anterior-insula / salience
    activation forecasts LOWER engagement. So for activation above each
    construct's baseline mean, the reward-positive `reward` sub-score must rise
    above 50 while the sign-inverted `emotion` sub-score must fall below 50.
    """
    preds = _make_preds_at_offset(t=5, offset_sigmas=+2.0)
    result = score_preds(preds, video_duration_s=2.0)
    assert result.sub_scores["reward"] > 50
    assert result.sub_scores["emotion"] < 50
    # The same inversion must hold in the per-timestep timeline.
    for row in result.timeline:
        assert row["reward"] > 50
        assert row["emotion"] < 50


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
