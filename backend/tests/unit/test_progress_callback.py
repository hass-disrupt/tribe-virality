"""Tests that backends correctly emit progress callbacks."""

from __future__ import annotations

import asyncio
import struct
from pathlib import Path

import pytest

from tribe_virality.inference.mock import MockBackend


def _create_dummy_video(path: Path) -> None:
    """Write a few bytes — enough for the mock backend's content-hash seed."""
    path.write_bytes(b"\x00\x00\x00\x20ftypmp42" + struct.pack(">I", 0xDEADBEEF) * 4)


@pytest.mark.asyncio
async def test_mock_backend_emits_progress(tmp_path):
    video = tmp_path / "v.mp4"
    _create_dummy_video(video)

    backend = MockBackend()
    events: list[tuple[int, str]] = []

    def cb(pct: int, label: str) -> None:
        events.append((pct, label))

    preds, segments = await backend.predict_fmri(video, duration_s=5.0, progress_cb=cb)

    assert preds.ndim == 2
    assert len(segments) == 1
    assert len(events) >= 2  # at least start + end
    pcts = [e[0] for e in events]
    # Progress must be monotonically non-decreasing
    assert pcts == sorted(pcts)
    # Final stage near complete
    assert events[-1][0] >= 90


@pytest.mark.asyncio
async def test_progress_cb_is_optional(tmp_path):
    """Backwards compat: predict_fmri without progress_cb still works."""
    video = tmp_path / "v.mp4"
    _create_dummy_video(video)

    backend = MockBackend()
    preds, segments = await backend.predict_fmri(video, duration_s=3.0)

    assert preds.ndim == 2
    assert len(segments) == 1


@pytest.mark.asyncio
async def test_queue_progress_cb_maps_to_outer_range():
    """Verify _make_progress_cb rescales backend's 0-100 into outer 30-65."""
    from tribe_virality.jobs.queue import JobQueue, JobState

    q = JobQueue()
    q._states["test_job"] = JobState(job_id="test_job", attempt_id="att_1")

    cb = q._make_progress_cb("test_job", base_pct=30, span_pct=35)
    cb(0, "start")
    assert q._states["test_job"].progress == 30
    cb(50, "middle")
    assert q._states["test_job"].progress == 47
    cb(100, "end")
    assert q._states["test_job"].progress == 65
    assert q._states["test_job"].stage_label == "end"
