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
from typing import Any

import numpy as np

from .baseline import load_baseline_stats
from .constants import SUB_SCORE_NAMES, WEIGHTS
from .rois import expected_n_vertices, get_bucket_indices


@dataclass(frozen=True)
class PipelineResult:
    headline_score: int
    sub_scores: dict[str, float]
    timeline: list[dict[str, float]]


def _sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    # Stable logistic sigmoid
    return 1.0 / (1.0 + np.exp(-x))


def _zscore_to_score(mean_activation: float, mu: float, sigma: float) -> float:
    """Map a scalar mean-activation to a 0-100 score via z-score + sigmoid."""
    z = (mean_activation - mu) / sigma
    # Sigmoid on z gives 0-1; map linearly to 0-100.
    return float(_sigmoid(z) * 100.0)


def _curve_to_0_100(curve: np.ndarray, mu: float, sigma: float) -> np.ndarray:
    """Map a (T,) activation curve to 0-100 per step, same z+sigmoid transform."""
    z = (curve - mu) / sigma
    return _sigmoid(z) * 100.0


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
        sub_scores[name] = round(_zscore_to_score(mean_activation, mu, sigma), 2)

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
        curves_0_100[name] = _curve_to_0_100(curves[name], mu, sigma)

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


def sub_score_curves(preds: np.ndarray) -> dict[str, np.ndarray]:
    """Return the raw (T,) curve per sub-score, pre-z-scoring.

    Used by the brain renderer, which colors the cortex by per-vertex activation
    but wants to know the per-sub-score envelope for legending.
    """
    bucket_indices = get_bucket_indices()
    return {name: preds[:, bucket_indices[name]].mean(axis=1).astype(np.float64) for name in SUB_SCORE_NAMES}


def serialize_result(result: PipelineResult) -> dict[str, Any]:
    """Produce a JSON-serializable dict for storage/transport."""
    return {
        "headline_score": int(result.headline_score),
        "sub_scores": {k: float(v) for k, v in result.sub_scores.items()},
        "timeline": [{k: float(v) for k, v in row.items()} for row in result.timeline],
    }
