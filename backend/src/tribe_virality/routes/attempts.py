"""Routes for reading and managing attempts."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse

from ..config import settings
from ..db import db_session
from ..models import AttemptRow, SessionRow
from ..schemas import AttemptResult, AttemptSummary, SubScores, TimelinePoint


router = APIRouter(prefix="/api")


def _row_to_result(row: AttemptRow) -> AttemptResult:
    sub_scores = None
    timeline = None
    if row.sub_scores_json:
        sub_scores = SubScores(**json.loads(row.sub_scores_json))
    if row.timeline_json:
        timeline = [TimelinePoint(**row) for row in json.loads(row.timeline_json)]
    return AttemptResult(
        attempt_id=row.attempt_id,
        label=row.label,
        uploaded_at=row.uploaded_at,
        status=row.status,
        video_filename=row.video_filename,
        video_duration_s=row.video_duration_s,
        headline_score=row.headline_score,
        sub_scores=sub_scores,
        timeline=timeline,
        has_brain_video=bool(row.has_brain_video),
        brain_frame_count=row.brain_frame_count or 0,
        error_message=row.error_message,
    )


@router.get("/attempts/{attempt_id}", response_model=AttemptResult)
async def get_attempt(
    attempt_id: str,
    x_session_id: str | None = Header(default=None),
) -> AttemptResult:
    with db_session() as s:
        row = s.get(AttemptRow, attempt_id)
        if row is None or (x_session_id and row.session_id != x_session_id):
            raise HTTPException(404, "attempt not found")
        return _row_to_result(row)


@router.get("/sessions/{session_id}/attempts", response_model=list[AttemptSummary])
async def list_attempts(session_id: str) -> list[AttemptSummary]:
    with db_session() as s:
        sess = s.get(SessionRow, session_id)
        if sess is None:
            return []
        rows = sorted(sess.attempts, key=lambda r: r.uploaded_at, reverse=True)
        return [
            AttemptSummary(
                attempt_id=r.attempt_id,
                label=r.label,
                uploaded_at=r.uploaded_at,
                status=r.status,
                headline_score=r.headline_score,
                video_duration_s=r.video_duration_s,
                has_brain_video=bool(r.has_brain_video),
            )
            for r in rows
        ]


@router.delete("/attempts/{attempt_id}")
async def delete_attempt(
    attempt_id: str,
    x_session_id: str | None = Header(default=None),
) -> dict:
    with db_session() as s:
        row = s.get(AttemptRow, attempt_id)
        if row is None or (x_session_id and row.session_id != x_session_id):
            raise HTTPException(404, "attempt not found")

        # Remove files.
        upload_path = settings.uploads_dir / row.video_filename
        upload_path.unlink(missing_ok=True)
        result_dir = settings.results_dir / attempt_id
        if result_dir.exists():
            for child in result_dir.rglob("*"):
                if child.is_file():
                    child.unlink()
            for child in sorted(result_dir.rglob("*"), reverse=True):
                if child.is_dir():
                    child.rmdir()
            result_dir.rmdir()

        s.delete(row)
    return {"ok": True}


@router.get("/attempts/{attempt_id}/video")
async def get_attempt_video(attempt_id: str) -> FileResponse:
    with db_session() as s:
        row = s.get(AttemptRow, attempt_id)
        if row is None:
            raise HTTPException(404, "attempt not found")
        path = settings.uploads_dir / row.video_filename
    if not path.exists():
        raise HTTPException(404, "video not found")
    return FileResponse(path, media_type="video/mp4")


@router.get("/attempts/{attempt_id}/brain.mp4")
async def get_attempt_brain(attempt_id: str) -> FileResponse:
    path = settings.results_dir / attempt_id / "brain.mp4"
    if not path.exists():
        raise HTTPException(404, "brain video not available")
    return FileResponse(path, media_type="video/mp4")


@router.get("/attempts/{attempt_id}/thumbnails/{second}.jpg")
async def get_attempt_thumbnail(attempt_id: str, second: int) -> FileResponse:
    path = settings.results_dir / attempt_id / "thumbnails" / f"{second}.jpg"
    if not path.exists():
        raise HTTPException(404, "thumbnail not found")
    return FileResponse(path, media_type="image/jpeg")


@router.get("/attempts/{attempt_id}/brain-frames/{frame_idx}.jpg")
async def get_brain_frame(attempt_id: str, frame_idx: int) -> FileResponse:
    path = settings.results_dir / attempt_id / "brain_frames" / f"frame_{frame_idx:03d}.jpg"
    if not path.exists():
        raise HTTPException(404, "brain frame not found")
    return FileResponse(path, media_type="image/jpeg")
