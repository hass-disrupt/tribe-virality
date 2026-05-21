#!/usr/bin/env python3
"""Build an empirical baseline_stats.json from saved Replicate prediction JSONs.

Workflow (no local GPU required):

    1. Pick ~20-30 generic short video clips. Engagement/virality labels are
       NOT required — the baseline only needs to characterise a "typical"
       video. Real natural content (not blank/static clips) gives the best
       distribution.
    2. Run each clip through your existing Replicate model and save the
       prediction JSON output to a directory (one file per clip).
    3. Run this script:
           python cog/data/build_baseline_from_predictions.py /path/to/json_dir
       It inverts each sub-score back to TRIBE's native activation units,
       aggregates the per-clip means, and rewrites cog/data/baseline_stats.json
       with empirical μ/σ.
    4. Re-push cog. Future predictions z-score against the real distribution
       and the sub-scores spread meaningfully across 0-100.

The inversion assumes the predictions were produced by scoring_version 2.0
with the synthetic baseline (μ=0.5, σ=0.15). Mixing other scoring versions in
the directory will skew the baseline; the script checks scoring_version and
skips mismatched files with a warning.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scoring.baseline_build import compute_baseline_stats  # noqa: E402
from scoring.constants import ROI_SIGN, SUB_SCORE_NAMES  # noqa: E402

# Synthetic baseline μ/σ that produced the sub-scores we'll invert. Must match
# the values that were in baseline_stats.json when the predictions were made.
SYNTHETIC_MU = 0.5
SYNTHETIC_SIGMA = 0.15
EXPECTED_SCORING_VERSION = "2.0"

OUT_PATH = Path(__file__).resolve().parent / "baseline_stats.json"


def _logit(p: float) -> float:
    # Clamp so a 0 or 100 sub-score doesn't blow up to ±inf.
    p = max(min(p, 0.999), 0.001)
    return math.log(p / (1.0 - p))


def activation_from_score(name: str, score: float) -> float:
    """Invert the scorer's sigmoid mapping to recover the TRIBE activation.

    score = sigmoid(sign · (x − μ) / σ) · 100
        ⇒ x = μ + sign · σ · logit(score / 100)
    """
    sign = ROI_SIGN[name]
    return SYNTHETIC_MU + sign * SYNTHETIC_SIGMA * _logit(score / 100.0)


def per_video_means(payload: dict) -> dict[str, float]:
    """Return ``{construct: time-mean TRIBE activation}`` for one prediction."""
    output = payload["output"]
    sv = output.get("scoring_version")
    if sv != EXPECTED_SCORING_VERSION:
        raise ValueError(
            f"scoring_version {sv!r} != {EXPECTED_SCORING_VERSION!r}; "
            "inversion math assumes the current synthetic baseline"
        )
    timeline = output["timeline"]
    if not timeline:
        raise ValueError("empty timeline")
    sums = {n: 0.0 for n in SUB_SCORE_NAMES}
    for row in timeline:
        for n in SUB_SCORE_NAMES:
            sums[n] += activation_from_score(n, float(row[n]))
    n_rows = len(timeline)
    return {n: sums[n] / n_rows for n in SUB_SCORE_NAMES}


def aggregate_predictions(json_dir: Path) -> tuple[dict[str, list[float]], list[str]]:
    """Walk ``json_dir`` and return (per-video activations, skipped filenames)."""
    files = sorted(p for p in json_dir.iterdir() if p.suffix == ".json")
    per_video: dict[str, list[float]] = {n: [] for n in SUB_SCORE_NAMES}
    skipped: list[str] = []
    for f in files:
        try:
            with f.open() as fp:
                payload = json.load(fp)
            means = per_video_means(payload)
        except Exception as e:
            print(f"  skip {f.name}: {e}", file=sys.stderr)
            skipped.append(f.name)
            continue
        for n in SUB_SCORE_NAMES:
            per_video[n].append(means[n])
        print(f"  ok   {f.name}")
    return per_video, skipped


def main(json_dir: str) -> None:
    dir_path = Path(json_dir).resolve()
    if not dir_path.is_dir():
        raise SystemExit(f"Not a directory: {dir_path}")
    per_video, skipped = aggregate_predictions(dir_path)
    n_clips = len(next(iter(per_video.values())))
    if n_clips < 2:
        raise SystemExit(
            f"Need at least 2 valid prediction JSONs to compute std; got {n_clips}"
        )

    stats = compute_baseline_stats(per_video)
    payload = {
        "_comment": (
            f"Empirical baseline computed by "
            f"build_baseline_from_predictions.py from {n_clips} Replicate "
            f"prediction JSONs on {date.today().isoformat()}. Mean/std of "
            f"per-construct activation in TRIBE's native output units, "
            f"recovered by inverting the synthetic-baseline sigmoid."
        ),
        "provenance": "empirical",
        **stats,
    }
    with OUT_PATH.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(
        f"\nWrote {OUT_PATH}\n"
        f"  clips aggregated: {n_clips}\n"
        f"  clips skipped:    {len(skipped)}\n"
    )
    for name in SUB_SCORE_NAMES:
        print(
            f"  {name:<17} μ={stats[name]['mean']:+.4f}  "
            f"σ={stats[name]['std']:.4f}  "
            f"(n={stats[name]['n_videos']})"
        )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: build_baseline_from_predictions.py <dir-of-prediction-jsons>"
        )
    main(sys.argv[1])
