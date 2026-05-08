"""Cog Predictor for TRIBE Virality.

Phase 1 (this file): synthesizes a plausible timeline from video duration so
the frontend can be developed end-to-end against a real Replicate model.
Phase 2 (TODO, manual): wire facebook/tribev2 inside `predict()`.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import numpy as np
from cog import BasePredictor, Input, Path as CogPath
from pydantic import BaseModel

from scoring.constants import SUB_SCORE_NAMES
from scoring.pipeline import score_preds
from scoring.rois import expected_n_vertices

SCORING_VERSION = "1.0"
MODEL_VERSION = "synthetic-v1"  # will become "tribev2-<commit>" after Phase 2
TRIBE_OUTPUT_HZ = 2.0  # TRIBE v2 emits ~2 fMRI frames per second
MIN_TIMESTEPS = 4  # below this, the synthetic sinusoid degenerates to flat


class TribeOutput(BaseModel):
    headline_score: int
    sub_scores: dict[str, int]
    timeline: list[dict[str, float]]
    video_duration_s: float
    frame_count: int
    model_version: str
    scoring_version: str


def _ffprobe_duration_s(video_path: Path) -> float:
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(video_path),
            ],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed: {e.stderr.strip() or 'no stderr'}") from e
    text = out.stdout.strip()
    if not text:
        raise RuntimeError("ffprobe produced no duration output")
    return float(text)


def _seed_from_video(video_path: Path) -> int:
    """Hash the file's first 1 MB into a 32-bit seed.

    Capped at 1 MB so seeding stays cheap on large videos. Two different videos
    with identical first 1 MB will collide — acceptable for synthetic Phase-1
    output but worth knowing for tests.
    """
    h = hashlib.sha256()
    with video_path.open("rb") as f:
        h.update(f.read(1024 * 1024))
    return int.from_bytes(h.digest()[:4], "big")


def _synth_preds(seed: int, t: int, v: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = np.full((t, v), 0.5, dtype=np.float64)
    base += rng.normal(0.0, 0.04, size=(1, v))
    phases = rng.uniform(0, 2 * np.pi, size=(1, v))
    times = np.linspace(0, 2 * np.pi * 2, num=t).reshape(-1, 1)
    base += 0.08 * np.sin(times + phases)
    return np.clip(base, 0.0, 1.0)


class Predictor(BasePredictor):
    def setup(self) -> None:
        from scoring.baseline import load_baseline_stats
        from scoring.rois import get_bucket_indices, load_roi_mapping
        load_roi_mapping()
        load_baseline_stats()
        get_bucket_indices()

    def predict(  # type: ignore[override]
        self,
        video: CogPath = Input(description="Video file (≤60s, MP4/MOV/WebM)"),
    ) -> TribeOutput:
        print("STAGE:loading_video", flush=True)
        video_path = Path(video)
        duration_s = _ffprobe_duration_s(video_path)
        if duration_s <= 0:
            raise ValueError(f"Invalid duration: {duration_s}")
        t = max(MIN_TIMESTEPS, int(round(duration_s * TRIBE_OUTPUT_HZ)))
        v = expected_n_vertices()

        print("STAGE:tribe_inference", flush=True)
        seed = _seed_from_video(video_path)
        preds = _synth_preds(seed, t, v)

        print("STAGE:scoring", flush=True)
        result = score_preds(preds, video_duration_s=duration_s)

        print("STAGE:done", flush=True)
        return TribeOutput(
            headline_score=int(result.headline_score),
            sub_scores={k: int(round(result.sub_scores[k])) for k in SUB_SCORE_NAMES},
            timeline=[{k: float(v) for k, v in row.items()} for row in result.timeline],
            video_duration_s=float(duration_s),
            frame_count=len(result.timeline),
            model_version=MODEL_VERSION,
            scoring_version=SCORING_VERSION,
        )
