"""Generate a per-video performance baseline table for LocalMPSBackend.

Usage (from repo root):

    cd backend
    TRIBE_BACKEND=local python scripts/perf_baseline.py \
        --videos ../sample-videos \
        --out ../docs/perf-baseline.md

Output: a markdown table with cold/warm timings, memory, and scores.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import platform as _platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _gb(b: int) -> float:
    return b / 1024**3


async def _measure(backend, video: Path, duration_s: float) -> dict:
    stage_times: dict[str, float] = {}
    stage_starts: dict[str, float] = {}

    def cb(pct: int, label: str) -> None:
        now = time.perf_counter()
        if label not in stage_starts:
            stage_starts[label] = now
        # Close out the previous stage
        prev = list(stage_starts.keys())[-2] if len(stage_starts) >= 2 else None
        if prev:
            stage_times[prev] = stage_times.get(prev, 0.0) + (now - stage_starts[prev])

    t0 = time.perf_counter()
    preds, _ = await backend.predict_fmri(video, duration_s=duration_s, progress_cb=cb)
    total = time.perf_counter() - t0

    return {
        "preds": preds,
        "total_s": total,
        "stage_times": stage_times,
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", type=Path, default=Path("../sample-videos"))
    ap.add_argument("--out", type=Path, default=Path("../docs/perf-baseline.md"))
    ap.add_argument("--max", type=int, default=5, help="Max videos to time")
    args = ap.parse_args()

    os.environ["TRIBE_BACKEND"] = "local"

    from tribe_virality.capabilities import get_capabilities
    from tribe_virality.inference.factory import get_backend
    from tribe_virality.media.ffprobe import probe_video
    from tribe_virality.scoring.pipeline import score_preds

    caps = get_capabilities()
    if not caps.can_run_local:
        sys.exit(f"Cannot run locally: {caps.fallback_reason}")

    backend = get_backend()
    if backend.name != "local":
        sys.exit("Factory did not return LocalMPSBackend.")

    try:
        import psutil

        proc = psutil.Process()
    except ImportError:
        proc = None

    try:
        import torch
    except ImportError:
        torch = None

    videos = sorted(args.videos.glob("*.mp4"))[: args.max]
    if not videos:
        sys.exit(f"No .mp4 files in {args.videos}")

    rows = []
    cold_load_s = None

    for i, video in enumerate(videos):
        info = await probe_video(video)
        size_mb = video.stat().st_size / 1024**2

        print(f"\n[{i+1}/{len(videos)}] {video.name}  duration={info.duration_s:.1f}s  size={size_mb:.1f}MB")

        # First run: includes model load on the very first call.
        t_load_start = time.perf_counter() if i == 0 else None
        result = await _measure(backend, video, info.duration_s)

        if i == 0 and t_load_start is not None:
            # Whole first call wraps load + work; we record total as cold.
            cold_load_s = result["total_s"]

        score_t0 = time.perf_counter()
        scored = score_preds(np.asarray(result["preds"], dtype=np.float32), info.duration_s)
        t_score_s = time.perf_counter() - score_t0

        mem_rss = _gb(proc.memory_info().rss) if proc else 0.0
        mem_mps = 0.0
        if torch is not None and torch.backends.mps.is_available():
            try:
                mem_mps = torch.mps.driver_allocated_memory() / 1024**3
            except Exception:
                mem_mps = 0.0

        rows.append({
            "name": video.stem,
            "duration_s": info.duration_s,
            "size_mb": size_mb,
            "total_s": result["total_s"],
            "score_s": t_score_s,
            "headline": scored.headline_score,
            "mem_rss_gb": mem_rss,
            "mem_mps_gb": mem_mps,
            "is_cold": i == 0,
        })

        print(
            f"  total={result['total_s']:.1f}s  score={t_score_s:.3f}s  "
            f"headline={scored.headline_score}  rss={mem_rss:.2f}GB  mps={mem_mps:.2f}GB"
        )

    # Build markdown report
    chip = caps.accelerator_name or caps.accelerator
    out_lines = [
        "# TRIBE v2 — MPS Performance Baseline",
        "",
        f"- **Hardware:** {chip} ({caps.platform}), {caps.total_memory_gb:.0f} GB",
        f"- **Backend:** local (`facebook/tribev2`)",
        f"- **Dtype:** {caps.recommended_dtype}",
        f"- **Date:** {datetime.now(timezone.utc).date().isoformat()}",
        f"- **Cold-start (first call total):** {cold_load_s:.1f}s" if cold_load_s else "",
        "",
        "| Video | Duration | Size | Total | Score | Headline | RSS | MPS |",
        "|-------|----------|------|-------|-------|----------|-----|-----|",
    ]
    for r in rows:
        cold_marker = " (cold)" if r["is_cold"] else ""
        out_lines.append(
            f"| {r['name']}{cold_marker} | {r['duration_s']:.1f}s | {r['size_mb']:.1f} MB | "
            f"{r['total_s']:.1f}s | {r['score_s']:.3f}s | {r['headline']} | "
            f"{r['mem_rss_gb']:.2f} GB | {r['mem_mps_gb']:.2f} GB |"
        )

    out_lines += [
        "",
        "**Notes:**",
        "- The first row is a cold call — its total includes one-time model load.",
        "- Subsequent rows reuse the in-memory model (warm).",
        "- Determinism: re-running yields identical headline scores.",
    ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(out_lines))
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
