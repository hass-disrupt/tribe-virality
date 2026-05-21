"""Pure aggregation for empirical baseline statistics.

Given the per-construct mean activation for each of N reference videos (no
engagement labels needed — only *typical* clips), compute the mean/std used to
z-score a new video. Kept separate from the TRIBE/IO shell in
``data/build_baseline_stats.py`` so it is unit-testable without a GPU.
"""

from __future__ import annotations

import numpy as np

from .constants import SUB_SCORE_NAMES

MIN_REFERENCE_VIDEOS = 2  # >=2 needed for a non-degenerate std; ~30 recommended.


def compute_baseline_stats(
    per_video: dict[str, list[float]],
) -> dict[str, dict[str, float]]:
    """Aggregate per-video activations into ``{construct: {mean, std, n_videos}}``.

    Raises ``KeyError`` if a sub-score is missing, and ``ValueError`` for too
    few videos or zero variance (a constant baseline makes z-scores undefined).
    """
    out: dict[str, dict[str, float]] = {}
    for name in SUB_SCORE_NAMES:
        if name not in per_video:
            raise KeyError(f"Sub-score {name!r} missing from per-video activations")
        vals = np.asarray(per_video[name], dtype=np.float64).ravel()
        if vals.size < MIN_REFERENCE_VIDEOS:
            raise ValueError(
                f"{name!r}: need at least {MIN_REFERENCE_VIDEOS} reference "
                f"videos, got {vals.size}"
            )
        mean = float(vals.mean())
        std = float(vals.std())  # population std (ddof=0)
        if not std > 0:
            raise ValueError(
                f"{name!r}: zero variance across reference videos (constant "
                "activation) — std must be > 0 to z-score"
            )
        out[name] = {"mean": mean, "std": std, "n_videos": int(vals.size)}
    return out
