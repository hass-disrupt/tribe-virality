"""Smoke test the LocalMPSBackend on a single sample video.

Usage (from repo root):

    cd backend
    TRIBE_BACKEND=local python scripts/smoke_local.py ../sample-videos/vid1.mp4

Reports:
    - Capabilities (tier, accelerator, memory, dtype)
    - Cold-start model load time (first call only)
    - Per-stage timings: features, predict, score
    - Memory: process RSS before/after, peak MPS allocation
    - Headline + sub-scores
    - Second-run (warm) timing
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

# Ensure project root is importable when run directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _bytes_to_gb(b: int) -> float:
    return b / 1024**3


async def _run_one(backend, video: Path, duration_s: float, label: str) -> dict:
    events: list[tuple[float, int, str]] = []  # (elapsed_s, pct, label)
    t0 = time.perf_counter()

    def cb(pct: int, lbl: str) -> None:
        events.append((time.perf_counter() - t0, pct, lbl))
        print(f"  [{events[-1][0]:5.1f}s] {pct:3d}%  {lbl}")

    preds, segments = await backend.predict_fmri(video, duration_s=duration_s, progress_cb=cb)
    total = time.perf_counter() - t0
    print(f"  {label} total: {total:.1f}s  preds.shape={preds.shape}")

    return {
        "preds": preds,
        "segments": segments,
        "events": events,
        "total_s": total,
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path, help="Path to sample video")
    ap.add_argument("--repeat", type=int, default=2, help="Number of timed runs")
    args = ap.parse_args()

    if not args.video.exists():
        sys.exit(f"Video not found: {args.video}")

    # Force local backend for the duration of this script
    os.environ["TRIBE_BACKEND"] = "local"

    from tribe_virality.capabilities import get_capabilities
    from tribe_virality.inference.factory import get_backend
    from tribe_virality.media.ffprobe import probe_video
    from tribe_virality.scoring.pipeline import score_preds

    print("== Capabilities ==")
    caps = get_capabilities()
    print(json.dumps(caps.to_dict(), indent=2))
    if not caps.can_run_local:
        sys.exit(f"\nCannot run locally: {caps.fallback_reason}")

    info = await probe_video(args.video)
    print(f"\nVideo: {args.video.name}  duration={info.duration_s:.1f}s")

    # Build the actual backend (factory may downgrade if init fails)
    backend = get_backend()
    print(f"Active backend: {backend.name}")
    if backend.name != "local":
        sys.exit("Factory did not return LocalMPSBackend (initialization failed?). Check logs.")

    # Memory reporting helpers
    try:
        import psutil

        proc = psutil.Process()
    except ImportError:
        proc = None

    try:
        import torch
    except ImportError:
        torch = None

    rss_before = _bytes_to_gb(proc.memory_info().rss) if proc else 0.0

    # Run N times
    runs = []
    for i in range(args.repeat):
        print(f"\n== Run {i + 1}/{args.repeat} ==")
        result = await _run_one(backend, args.video, info.duration_s, f"run{i+1}")
        runs.append(result)

        # Memory snapshot after each run
        if proc:
            rss = _bytes_to_gb(proc.memory_info().rss)
            print(f"  RSS: {rss:.2f} GB")
        if torch is not None and torch.backends.mps.is_available():
            try:
                allocated = torch.mps.driver_allocated_memory() / 1024**3
                print(f"  MPS allocated: {allocated:.2f} GB")
            except Exception:
                pass

    # Score the first run's preds
    print("\n== Scoring (run 1) ==")
    t0 = time.perf_counter()
    result = score_preds(np.asarray(runs[0]["preds"], dtype=np.float32), info.duration_s)
    print(f"  Scoring took {time.perf_counter() - t0:.3f}s")
    print(f"  Headline: {result.headline_score}")
    print(f"  Sub-scores: {json.dumps(result.sub_scores, indent=4)}")

    # Determinism check across runs
    if args.repeat >= 2:
        h1 = score_preds(np.asarray(runs[0]["preds"], dtype=np.float32), info.duration_s).headline_score
        h2 = score_preds(np.asarray(runs[1]["preds"], dtype=np.float32), info.duration_s).headline_score
        print(f"\nDeterminism: run1={h1}  run2={h2}  match={h1 == h2}")

    print(f"\nFinal RSS: {_bytes_to_gb(proc.memory_info().rss):.2f} GB (was {rss_before:.2f} GB)" if proc else "")


if __name__ == "__main__":
    asyncio.run(main())
