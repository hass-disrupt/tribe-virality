"""Tests for the empirical-baseline-from-Replicate-JSONs helper."""

from __future__ import annotations

import json
import math

import pytest

from scoring.constants import ROI_SIGN, SUB_SCORE_NAMES


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def _forward_score(name: str, activation: float, mu: float, sigma: float) -> float:
    """Reference implementation of the scorer's forward mapping."""
    z = ROI_SIGN[name] * (activation - mu) / sigma
    return _sigmoid(z) * 100.0


def test_activation_from_score_is_inverse_of_the_scorer():
    """Forward (act → score) followed by inverse must round-trip every construct."""
    from data.build_baseline_from_predictions import (
        SYNTHETIC_MU,
        SYNTHETIC_SIGMA,
        activation_from_score,
    )

    for name in SUB_SCORE_NAMES:
        for act in (-0.5, -0.05, 0.0, 0.05, 0.2, 0.5):
            score = _forward_score(name, act, SYNTHETIC_MU, SYNTHETIC_SIGMA)
            recovered = activation_from_score(name, score)
            assert math.isclose(recovered, act, abs_tol=1e-6), (
                f"{name}: {act} -> {score} -> {recovered}"
            )


def test_activation_from_score_handles_extreme_sub_scores_without_overflow():
    from data.build_baseline_from_predictions import activation_from_score

    # Saturated 0 and 100 must still produce finite numbers (logit clamp).
    for name in SUB_SCORE_NAMES:
        assert math.isfinite(activation_from_score(name, 0.0))
        assert math.isfinite(activation_from_score(name, 100.0))


def test_per_video_means_averages_timeline_in_activation_units():
    from data.build_baseline_from_predictions import per_video_means

    payload = {
        "output": {
            "scoring_version": "2.0",
            "timeline": [
                # All scores = 50 → activations exactly at the synthetic mean.
                {"t": 0.0, **{n: 50.0 for n in SUB_SCORE_NAMES}},
                {"t": 1.0, **{n: 50.0 for n in SUB_SCORE_NAMES}},
            ],
        }
    }
    means = per_video_means(payload)
    for name in SUB_SCORE_NAMES:
        assert math.isclose(means[name], 0.5, abs_tol=1e-6)


def test_per_video_means_rejects_wrong_scoring_version():
    from data.build_baseline_from_predictions import per_video_means

    payload = {
        "output": {
            "scoring_version": "1.0",
            "timeline": [{"t": 0.0, **{n: 50.0 for n in SUB_SCORE_NAMES}}],
        }
    }
    with pytest.raises(ValueError, match="scoring_version"):
        per_video_means(payload)


def test_aggregate_predictions_skips_bad_files_and_collects_good_ones(tmp_path):
    from data.build_baseline_from_predictions import aggregate_predictions

    # Two valid clips, one with empty timeline, one not a JSON at all.
    good_a = {
        "output": {
            "scoring_version": "2.0",
            "timeline": [{"t": 0.0, **{n: 50.0 for n in SUB_SCORE_NAMES}}],
        }
    }
    good_b = {
        "output": {
            "scoring_version": "2.0",
            "timeline": [{"t": 0.0, **{n: 70.0 for n in SUB_SCORE_NAMES}}],
        }
    }
    bad_empty = {"output": {"scoring_version": "2.0", "timeline": []}}

    (tmp_path / "a.json").write_text(json.dumps(good_a))
    (tmp_path / "b.json").write_text(json.dumps(good_b))
    (tmp_path / "c.json").write_text(json.dumps(bad_empty))
    (tmp_path / "not_json.json").write_text("{not valid json")

    per_video, skipped = aggregate_predictions(tmp_path)
    for name in SUB_SCORE_NAMES:
        assert len(per_video[name]) == 2
    assert {"c.json", "not_json.json"} == set(skipped)
