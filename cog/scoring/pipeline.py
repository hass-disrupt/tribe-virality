"""Pure scoring pipeline: preds -> sub-scores + headline + timeline.

Inputs
------
preds : np.ndarray of shape (T, V)
    T = timesteps (fMRI-rate, e.g. ~2 Hz output of TRIBE v2)
    V = cortical vertices (expected: fsaverage5 ~ 20484)
video_duration_s : float
    Used to build the time axis for the timeline.

Outputs
-------
PipelineResult with:
  headline_score   : int in [0, 100]
  sub_scores       : dict[sub_score_name -> float 0-100]
  timeline         : list of dict rows (one per TRIBE timestep),
                     each with "t" (seconds) plus one float per sub-score
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .baseline import load_baseline_stats
from .constants import ROI_SIGN, SUB_SCORE_NAMES, WEIGHTS
from .rois import expected_n_vertices, get_bucket_indices


@dataclass(frozen=True)
class PipelineResult:
    headline_score: int
    sub_scores: dict[str, float]
    timeline: list[dict[str, float]]


def _sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    # Stable logistic sigmoid
    return 1.0 / (1.0 + np.exp(-x))


def _zscore_to_score(
    mean_activation: float, mu: float, sigma: float, sign: int = 1
) -> float:
    """Map a scalar mean-activation to a 0-100 score via z-score + sigmoid.

    `sign` (+1/-1) flips the direction *before* the sigmoid so a construct whose
    higher activation predicts LOWER engagement (e.g. anterior insula) scores
    below 50 when above baseline. At baseline (z=0) the score is 50 either way.
    """
    z = sign * (mean_activation - mu) / sigma
    # Sigmoid on z gives 0-1; map linearly to 0-100.
    return float(_sigmoid(z) * 100.0)


def _curve_to_0_100(
    curve: np.ndarray, mu: float, sigma: float, sign: int = 1
) -> np.ndarray:
    """Map a (T,) activation curve to 0-100 per step, same signed z+sigmoid."""
    z = sign * (curve - mu) / sigma
    return _sigmoid(z) * 100.0


def roi_mean_activations(preds: np.ndarray) -> dict[str, float]:
    """Time-and-vertex-averaged activation per construct (the pre-z-score
    quantity). Reused by ``data/build_baseline_stats.py`` so empirical baselines
    are computed in TRIBE's native output units, on the same ROIs the scorer
    uses. Equals ``preds[:, idx].mean()`` for each bucket.
    """
    if preds.ndim != 2:
        raise ValueError(f"preds must be 2D (T, V); got shape {preds.shape}")
    expected_v = expected_n_vertices()
    if preds.shape[1] != expected_v:
        raise ValueError(
            f"preds has V={preds.shape[1]} vertices but ROI mapping expects "
            f"{expected_v}."
        )
    bucket_indices = get_bucket_indices()
    return {
        name: float(preds[:, bucket_indices[name]].mean())
        for name in SUB_SCORE_NAMES
    }


def score_preds(preds: np.ndarray, video_duration_s: float) -> PipelineResult:
    """Run the scoring pipeline.

    Parameters
    ----------
    preds : np.ndarray, shape (T, V), float
    video_duration_s : float, must be > 0

    Returns
    -------
    PipelineResult
    """
    if preds.ndim != 2:
        raise ValueError(f"preds must be 2D (T, V); got shape {preds.shape}")
    if video_duration_s <= 0:
        raise ValueError("video_duration_s must be > 0")

    t, v = preds.shape
    expected_v = expected_n_vertices()
    if v != expected_v:
        raise ValueError(
            f"preds has V={v} vertices but ROI mapping expects {expected_v}. "
            "Regenerate roi_mapping.json or align TRIBE output."
        )
    if t < 1:
        raise ValueError("preds must have at least one timestep")

    bucket_indices = get_bucket_indices()
    baseline = load_baseline_stats()

    # Per-timestep curves: (T,) per sub-score, averaged over its ROI vertices.
    curves: dict[str, np.ndarray] = {}
    for name in SUB_SCORE_NAMES:
        idx = bucket_indices[name]
        # preds[:, idx] has shape (T, len(idx)); mean over axis=1 -> (T,)
        curves[name] = preds[:, idx].mean(axis=1).astype(np.float64)

    # Per-sub-score headline: mean of the curve over time, z+sigmoid to 0-100.
    sub_scores: dict[str, float] = {}
    for name in SUB_SCORE_NAMES:
        mu = baseline[name]["mean"]
        sigma = baseline[name]["std"]
        mean_activation = float(curves[name].mean())
        sub_scores[name] = round(
            _zscore_to_score(mean_activation, mu, sigma, ROI_SIGN[name]), 2
        )

    # Weighted headline virality.
    headline_raw = sum(WEIGHTS[name] * sub_scores[name] for name in SUB_SCORE_NAMES)
    headline_score = int(round(headline_raw))
    headline_score = max(0, min(100, headline_score))

    # Timeline: one row per TRIBE timestep, mapped to 0-100 via the same transform.
    # t-axis spans [0, video_duration_s] with T points.
    if t == 1:
        times = np.array([0.0])
    else:
        times = np.linspace(0.0, video_duration_s, num=t, dtype=np.float64)

    # Precompute per-sub-score 0-100 curves.
    curves_0_100: dict[str, np.ndarray] = {}
    for name in SUB_SCORE_NAMES:
        mu = baseline[name]["mean"]
        sigma = baseline[name]["std"]
        curves_0_100[name] = _curve_to_0_100(curves[name], mu, sigma, ROI_SIGN[name])

    timeline: list[dict[str, float]] = []
    for i in range(t):
        row: dict[str, float] = {"t": float(times[i])}
        for name in SUB_SCORE_NAMES:
            row[name] = round(float(curves_0_100[name][i]), 2)
        timeline.append(row)

    return PipelineResult(
        headline_score=headline_score,
        sub_scores=sub_scores,
        timeline=timeline,
    )
