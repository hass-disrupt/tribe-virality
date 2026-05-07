"""Mock inference backend — produces plausible synthetic fMRI signals.

Design: we want the mock to (a) be deterministic given a video's content hash,
so re-uploading the same file yields the same score; (b) produce varied and
interesting signals across the five sub-score ROIs so the UI has something
compelling to render.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Optional

import numpy as np

from ..scoring.constants import SUB_SCORE_NAMES
from ..scoring.rois import expected_n_vertices, get_bucket_indices
from .backend import InferenceBackend, ProgressCallback, Segment


_FMRI_HZ = 2.0  # ~TRIBE v2 effective output rate


def _content_seed(path: Path) -> int:
    """Derive a deterministic 32-bit seed from the file content."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return int.from_bytes(h.digest()[:4], "big", signed=False)


def _smoothed_noise(rng: np.random.Generator, length: int, sigma: float) -> np.ndarray:
    """1D Gaussian-smoothed noise of given length."""
    raw = rng.standard_normal(length)
    if length <= 1 or sigma <= 0:
        return raw
    # Simple causal moving-average smoothing — no scipy dep.
    window = max(1, int(round(sigma)))
    kernel = np.ones(window, dtype=np.float64) / window
    padded = np.concatenate([np.full(window - 1, raw[0]), raw])
    return np.convolve(padded, kernel, mode="valid")


class MockBackend:
    """Generates smoothed synthetic fMRI with region-specific baselines."""

    name = "mock"

    async def predict_fmri(
        self,
        video_path: Path,
        duration_s: float,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> tuple[np.ndarray, list[Segment]]:
        # Yield to the event loop a few times to mimic real work.
        if progress_cb:
            progress_cb(10, "Generating synthetic activity")
        await asyncio.sleep(0.2)

        seed = _content_seed(video_path)
        rng = np.random.default_rng(seed)

        v = expected_n_vertices()
        t = max(2, int(round(duration_s * _FMRI_HZ)))
        if progress_cb:
            progress_cb(50, "Sampling per-region envelopes")

        # Per-bucket time envelopes: each sub-score gets its own smoothed curve
        # centered around a bucket-specific baseline.
        bucket_envelopes: dict[str, np.ndarray] = {}
        # Bucket-specific means (in the [0, 1] activation scale) vary by content
        # hash so different videos score differently.
        bucket_means: dict[str, float] = {}
        for name in SUB_SCORE_NAMES:
            mean_offset = rng.uniform(-0.2, 0.2)
            bucket_means[name] = 0.5 + mean_offset
            envelope = _smoothed_noise(rng, t, sigma=max(1.0, t / 8))
            # Normalize envelope to std 0.1 around bucket mean
            envelope = (envelope - envelope.mean()) / (envelope.std() + 1e-8) * 0.08
            bucket_envelopes[name] = envelope + bucket_means[name]

        # Build preds (T, V). Per-vertex = bucket envelope + per-vertex jitter.
        preds = np.empty((t, v), dtype=np.float32)
        # Default fill (vertices outside any bucket, if any): neutral 0.5.
        preds[:] = 0.5
        bucket_indices = get_bucket_indices()
        for name in SUB_SCORE_NAMES:
            idx = bucket_indices[name]
            envelope = bucket_envelopes[name]  # (T,)
            # Per-vertex jitter: (T, len(idx)) small gaussian, spatially correlated within bucket.
            jitter = rng.standard_normal((t, idx.size)).astype(np.float32) * 0.02
            preds[:, idx] = (envelope[:, None] + jitter).astype(np.float32)

        # Clip to plausible activation range.
        np.clip(preds, 0.0, 1.0, out=preds)

        if progress_cb:
            progress_cb(95, "Validating output")
        segments = [Segment(start_s=0.0, end_s=float(duration_s), n_timesteps=t)]
        return preds, segments
