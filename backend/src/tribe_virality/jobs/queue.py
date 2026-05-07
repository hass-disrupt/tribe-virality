"""In-process asyncio job queue with per-stage progress reporting."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from ..config import settings
from ..db import db_session
from ..inference import get_backend
from ..media.thumbnails import extract_thumbnails
from ..models import AttemptRow
from ..media.brain_frames import render_brain_frames
from ..scoring.pipeline import score_preds, serialize_result

log = logging.getLogger(__name__)


JobStatus = str  # queued|preprocessing|inferring|scoring|rendering|done|error


@dataclass
class JobState:
    job_id: str
    attempt_id: str
    status: JobStatus = "queued"
    progress: int = 0
    stage_label: str = "Queued"
    error_message: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "attempt_id": self.attempt_id,
            "status": self.status,
            "progress": self.progress,
            "stage_label": self.stage_label,
            "error_message": self.error_message,
        }


@dataclass
class _JobSpec:
    job_id: str
    attempt_id: str
    video_path: Path
    duration_s: float
    result_dir: Path


class JobQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[_JobSpec] = asyncio.Queue()
        self._states: dict[str, JobState] = {}
        self._worker_task: Optional[asyncio.Task] = None

    def ensure_worker_started(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            loop = asyncio.get_event_loop()
            self._worker_task = loop.create_task(self._worker_loop())

    def submit(self, job_id: str, attempt_id: str, video_path: Path, duration_s: float) -> None:
        result_dir = settings.results_dir / attempt_id
        result_dir.mkdir(parents=True, exist_ok=True)
        self._states[job_id] = JobState(
            job_id=job_id,
            attempt_id=attempt_id,
            status="queued",
            progress=2,
            stage_label="Queued",
        )
        self._queue.put_nowait(
            _JobSpec(job_id=job_id, attempt_id=attempt_id,
                     video_path=video_path, duration_s=duration_s,
                     result_dir=result_dir)
        )
        self.ensure_worker_started()

    def get_state(self, job_id: str) -> Optional[JobState]:
        return self._states.get(job_id)

    async def _worker_loop(self) -> None:
        while True:
            spec = await self._queue.get()
            try:
                await self._run_job(spec)
            except Exception:
                log.exception("Unhandled error in job worker")
            finally:
                self._queue.task_done()

    async def _render_brain_frames_bg(
        self, attempt_id: str, timeline: list, result_dir: Path
    ) -> None:
        brain_frames_dir = result_dir / "brain_frames"
        try:
            n_frames = await render_brain_frames(timeline, brain_frames_dir, max_frames=30)
            with db_session() as s:
                row = s.get(AttemptRow, attempt_id)
                if row:
                    row.brain_frame_count = n_frames
        except Exception as exc:
            log.warning("Brain frame rendering failed (non-fatal): %s", exc)

    def _update(self, job_id: str, **updates) -> None:
        state = self._states.get(job_id)
        if not state:
            return
        for k, v in updates.items():
            setattr(state, k, v)

    def _make_progress_cb(self, job_id: str, base_pct: int = 30, span_pct: int = 35):
        """Return a callback that maps backend's inner [0,100] pct into outer [base, base+span].

        Backends emit progress in 0-100 of *their* work. The job queue reserves
        30%-65% of the overall job for the inference stage, so we linearly
        rescale and overwrite the outer status to surface the sub-stage label.
        """

        def cb(inner_pct: int, label: str) -> None:
            inner = max(0, min(100, int(inner_pct)))
            outer = base_pct + int(span_pct * inner / 100)
            self._update(
                job_id,
                status="inferring",
                progress=outer,
                stage_label=label,
            )

        return cb

    async def _run_job(self, spec: _JobSpec) -> None:
        try:
            # Stage 1: preprocessing (thumbnails)
            self._update(spec.job_id, status="preprocessing", progress=10,
                         stage_label="Extracting frames")
            thumbnails_dir = spec.result_dir / "thumbnails"
            try:
                await extract_thumbnails(spec.video_path, thumbnails_dir, spec.duration_s)
            except Exception as exc:
                log.warning("Thumbnail extraction failed: %s", exc)

            # Stage 2: inference (backend emits sub-stage progress via callback)
            self._update(spec.job_id, status="inferring", progress=30,
                         stage_label="Predicting fMRI response")
            backend = get_backend()
            preds, _segments = await backend.predict_fmri(
                spec.video_path,
                spec.duration_s,
                progress_cb=self._make_progress_cb(spec.job_id),
            )

            # Stage 3: scoring
            self._update(spec.job_id, status="scoring", progress=65,
                         stage_label="Scoring brain response")
            result = score_preds(np.asarray(preds, dtype=np.float32), spec.duration_s)
            serialized = serialize_result(result)

            # Finalize DB row with scores — mark done immediately so the UI loads
            with db_session() as s:
                row = s.get(AttemptRow, spec.attempt_id)
                if row:
                    row.status = "done"
                    row.headline_score = serialized["headline_score"]
                    row.sub_scores_json = json.dumps(serialized["sub_scores"])
                    row.timeline_json = json.dumps(serialized["timeline"])
                    row.has_brain_video = 0

            # Mark job done so the Processing page navigates to Results right away
            self._update(spec.job_id, status="done", progress=100, stage_label="Done")

            # Fire-and-forget brain frame rendering — happens after job is "done"
            # so the user sees results immediately; frames appear as they finish.
            asyncio.get_event_loop().create_task(
                self._render_brain_frames_bg(spec.attempt_id, serialized["timeline"], spec.result_dir)
            )
        except Exception as exc:
            log.exception("Job %s failed", spec.job_id)
            with db_session() as s:
                row = s.get(AttemptRow, spec.attempt_id)
                if row:
                    row.status = "error"
                    row.error_message = str(exc)
            self._update(spec.job_id, status="error", progress=100,
                         stage_label="Error", error_message=str(exc))


_queue: Optional[JobQueue] = None


def get_queue() -> JobQueue:
    global _queue
    if _queue is None:
        _queue = JobQueue()
    return _queue
