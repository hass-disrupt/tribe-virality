#!/usr/bin/env python3
"""Regenerate cog/data/baseline_stats.json from real TRIBE runs.

Needs the cog image (baked TRIBE weights + GPU) and a small folder of ~20-30
*generic* reference clips. Engagement/virality labels are NOT required — the
baseline only characterises a "typical" video so a new clip can be z-scored.
Until this is run, scores are UNCALIBRATED (see METHODOLOGY.md).

The pure aggregation lives in scoring/baseline_build.py (unit-tested); this
script is the TRIBE/IO shell.

Usage (inside the cog image, GPU):
    cog run python cog/data/build_baseline_stats.py /path/to/reference_clips
    # review the diff, bump SCORING_VERSION, then commit baseline_stats.json
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from scoring.baseline_build import compute_baseline_stats  # noqa: E402
from scoring.constants import SUB_SCORE_NAMES  # noqa: E402
from scoring.pipeline import roi_mean_activations  # noqa: E402

OUT_PATH = Path(__file__).resolve().parent / "baseline_stats.json"
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}


def main(clips_dir: str) -> None:
    from tribev2.demo_utils import TribeModel  # local import: TRIBE only here

    clips = sorted(
        p for p in Path(clips_dir).iterdir() if p.suffix.lower() in VIDEO_EXTS
    )
    if not clips:
        raise SystemExit(f"No reference videos found in {clips_dir!r}")

    model = TribeModel.from_pretrained("facebook/tribev2")
    per_video: dict[str, list[float]] = {n: [] for n in SUB_SCORE_NAMES}
    for clip in clips:
        events = model.get_events_dataframe(video_path=str(clip))
        preds, _ = model.predict(events=events)
        preds = np.asarray(preds)
        for name, val in roi_mean_activations(preds).items():
            per_video[name].append(val)
        print(f"  processed {clip.name}")

    stats = compute_baseline_stats(per_video)
    payload = {
        "_comment": (
            f"Empirical baseline computed by build_baseline_stats.py from "
            f"{len(clips)} reference clips on {date.today().isoformat()}. "
            "Mean/std of per-construct activation in TRIBE's native output units."
        ),
        "provenance": "empirical",
        **stats,
    }
    with OUT_PATH.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"Wrote {OUT_PATH} from {len(clips)} clips")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: build_baseline_stats.py <reference_clips_dir>")
    main(sys.argv[1])
