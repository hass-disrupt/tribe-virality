"""Video probing. Uses ffprobe if available, else falls back to ffmpeg."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


class FFProbeError(RuntimeError):
    pass


@dataclass(frozen=True)
class VideoInfo:
    duration_s: float
    width: int
    height: int
    codec: str
    size_bytes: int


def _find_ffprobe() -> str | None:
    return shutil.which("ffprobe")


def _find_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


async def _probe_with_ffprobe(ffprobe: str, video_path: Path) -> VideoInfo:
    proc = await asyncio.create_subprocess_exec(
        ffprobe,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height",
        "-show_entries", "format=duration",
        "-of", "json",
        str(video_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise FFProbeError(f"ffprobe failed: {stderr.decode('utf-8', errors='replace')}")
    try:
        data = json.loads(stdout.decode("utf-8"))
        stream = data["streams"][0]
        duration = float(data["format"]["duration"])
        return VideoInfo(
            duration_s=duration,
            width=int(stream.get("width") or 0),
            height=int(stream.get("height") or 0),
            codec=str(stream.get("codec_name") or "unknown"),
            size_bytes=video_path.stat().st_size,
        )
    except (KeyError, IndexError, ValueError) as exc:
        raise FFProbeError(f"Could not parse ffprobe output: {exc}") from exc


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_STREAM_RE = re.compile(
    r"Stream\s+#\d+:\d+(?:\([^)]*\))?:\s+Video:\s+([\w/]+)[^,]*,\s+[^,]+,\s+(\d+)x(\d+)"
)


async def _probe_with_ffmpeg(ffmpeg: str, video_path: Path) -> VideoInfo:
    """Fallback when ffprobe is absent. ffmpeg prints format info on stderr."""
    proc = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-hide_banner",
        "-i", str(video_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr_bytes = await proc.communicate()
    # ffmpeg exits non-zero when no output is specified; we still want its stderr.
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    m = _DURATION_RE.search(stderr)
    if not m:
        raise FFProbeError(f"Could not parse duration from ffmpeg output: {stderr[:200]}")
    hours, minutes, seconds = int(m.group(1)), int(m.group(2)), float(m.group(3))
    duration = hours * 3600 + minutes * 60 + seconds

    codec = "unknown"
    width = 0
    height = 0
    sm = _STREAM_RE.search(stderr)
    if sm:
        codec = sm.group(1)
        width = int(sm.group(2))
        height = int(sm.group(3))

    return VideoInfo(
        duration_s=duration,
        width=width,
        height=height,
        codec=codec,
        size_bytes=video_path.stat().st_size,
    )


async def probe_video(video_path: Path) -> VideoInfo:
    """Probe a video. Prefer ffprobe, fall back to ffmpeg."""
    ffprobe = _find_ffprobe()
    if ffprobe:
        return await _probe_with_ffprobe(ffprobe, video_path)

    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        raise FFProbeError("Neither ffprobe nor ffmpeg found on PATH. Install ffmpeg.")
    return await _probe_with_ffmpeg(ffmpeg, video_path)
