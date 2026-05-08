"""Cog Predictor for TRIBE Virality.

Phase 2: real Meta TRIBE v2 inference.

Pipeline:
  video file
    -> tribev2.demo_utils.TribeModel.get_events_dataframe()  (extracts video/audio events)
    -> TribeModel.predict()                                  (runs the foundation model)
    -> (T, V) numpy preds on the fsaverage5 cortical mesh
    -> scoring.pipeline.score_preds()                        (cortical-proxy aggregation)
    -> 5 sub-scores + headline + per-step timeline
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from cog import BasePredictor, Input, Path as CogPath
from pydantic import BaseModel

from scoring.constants import SUB_SCORE_NAMES
from scoring.pipeline import score_preds

# Bumped any time the model weights, tokenizer pin, or scoring weights change.
# The frontend echoes this verbatim in attempt metadata so users can compare
# results across model revisions.
MODEL_VERSION = "tribev2-prod-v1"
SCORING_VERSION = "1.0"

# Where `cog.yaml`'s build step bakes the TRIBE weights. Must match the
# `cache_folder=` argument used in the bake command.
WEIGHTS_CACHE_DIR = Path("/src/cache")


class TribeOutput(BaseModel):
    headline_score: int
    sub_scores: dict[str, int]
    timeline: list[dict[str, float]]
    video_duration_s: float
    frame_count: int
    model_version: str
    scoring_version: str


def _ffprobe_duration_s(video_path: Path) -> float:
    """Return the duration of `video_path` in seconds via ffprobe."""
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


class Predictor(BasePredictor):
    def setup(self) -> None:
        # Imported here so module-level cog test discovery doesn't try to load
        # the heavy tribev2 stack on machines without it.
        from tribev2.demo_utils import TribeModel

        # Eager-load TRIBE from the cache that was baked at build time.
        # On the second worker boot this is a no-op; on the first boot it
        # paginates the weights into VRAM.
        print("STAGE:loading_model", flush=True)
        self.model = TribeModel.from_pretrained(
            "facebook/tribev2",
            cache_folder=str(WEIGHTS_CACHE_DIR),
        )

        # Eager-load the scoring caches (ROI mask + baseline stats) so the
        # first predict() call doesn't pay the JSON parse cost.
        from scoring.baseline import load_baseline_stats
        from scoring.rois import get_bucket_indices, load_roi_mapping

        load_roi_mapping()
        load_baseline_stats()
        get_bucket_indices()

    def predict(  # type: ignore[override]
        self,
        video: CogPath = Input(description="Video file (≤60s, MP4/MOV/WebM)"),
    ) -> TribeOutput:
        video_path = Path(video)

        print("STAGE:loading_video", flush=True)
        duration_s = _ffprobe_duration_s(video_path)
        if duration_s <= 0:
            raise ValueError(f"Invalid duration: {duration_s}")

        print("STAGE:tribe_inference", flush=True)
        # TRIBE first extracts an "events" table (transcribed audio segments,
        # video frames, etc.) and then predicts fMRI activation per cortical
        # vertex per timestep at ~2 Hz on the fsaverage5 mesh.
        events_df = self.model.get_events_dataframe(video_path=str(video_path))
        preds, _segments = self.model.predict(events=events_df)

        # `preds` is expected to be (T, V) on fsaverage5 (~20484 vertices).
        if not isinstance(preds, np.ndarray):
            preds = np.asarray(preds)
        if preds.ndim != 2:
            raise RuntimeError(
                f"TRIBE returned preds with shape {preds.shape}; expected (T, V)."
            )

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
