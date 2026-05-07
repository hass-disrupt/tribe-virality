"""Extract per-second thumbnail JPGs from a video via ffmpeg."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path


def _ensure_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError("ffmpeg not found on PATH. Install ffmpeg.")
    return path


async def extract_thumbnails(
    video_path: Path, out_dir: Path, duration_s: float, width: int = 240
) -> int:
    """Extract one JPG per second into out_dir/{second}.jpg (0-indexed).

    Returns the number of thumbnails produced.
    """
    ffmpeg = _ensure_ffmpeg()
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / "%d.jpg")

    # -start_number 0 makes thumbnails 0-indexed (0.jpg is at t=0).
    # -vf "fps=1,scale=W:-2" extracts 1 frame per second at the target width.
    proc = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-y",
        "-loglevel", "error",
        "-i", str(video_path),
        "-vf", f"fps=1,scale={width}:-2",
        "-start_number", "0",
        "-qscale:v", "4",
        pattern,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg thumbnail extraction failed: {stderr.decode('utf-8', errors='replace')}"
        )

    # Count generated thumbnails.
    return sum(1 for p in out_dir.glob("*.jpg"))
