"""Smoke test for the Predictor's end-to-end output.

Real TRIBE inference needs a GPU plus baked weights, so this test is
intentionally skipped on local CPU runs and CI. It is exercised inside
the cog image via `cog run python -m pytest`.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

cog = pytest.importorskip("cog")
pytest.importorskip("tribev2")

if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
    pytest.skip("ffmpeg/ffprobe not available", allow_module_level=True)

# Real TRIBE needs CUDA; the test is meaningful only inside the cog image.
try:
    import torch
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available — real TRIBE inference needs GPU", allow_module_level=True)
except ImportError:
    pytest.skip("torch not installed", allow_module_level=True)


@pytest.fixture
def tiny_mp4(tmp_path: Path) -> Path:
    out = tmp_path / "tiny.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=black:size=64x64:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out),
        ],
        check=True, capture_output=True,
    )
    return out


def test_predict_returns_well_formed_output(tiny_mp4: Path) -> None:
    from predict import Predictor

    predictor = Predictor()
    predictor.setup()
    result = predictor.predict(video=tiny_mp4)

    assert 0 <= result.headline_score <= 100
    assert set(result.sub_scores.keys()) == {
        "reward", "emotion", "attention", "novelty", "social_relevance",
    }
    for v in result.sub_scores.values():
        assert 0 <= v <= 100
    assert result.frame_count == len(result.timeline)
    assert result.frame_count >= 2
    assert result.video_duration_s > 0
    for row in result.timeline:
        assert "t" in row
        for k in result.sub_scores:
            assert 0 <= row[k] <= 100

    # Non-degeneracy: real TRIBE preds should vary over time. A flat
    # timeline indicates a wiring bug (e.g. mean preds being passed
    # instead of per-step values).
    reward_values = {row["reward"] for row in result.timeline}
    assert len(reward_values) > 1, "Timeline reward column is flat — TRIBE output suspicious"

    assert result.model_version.startswith("tribev2"), \
        f"Unexpected model_version: {result.model_version}"
