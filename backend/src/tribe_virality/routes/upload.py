"""POST /api/upload — validate and enqueue inference."""

from __future__ import annotations

import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from ..config import settings
from ..db import db_session
from ..jobs import get_queue
from ..media.ffprobe import FFProbeError, probe_video
from ..models import AttemptRow, SessionRow
from ..schemas import UploadResponse


router = APIRouter(prefix="/api")


@router.post("/upload", response_model=UploadResponse)
async def upload(
    video: UploadFile = File(...),
    x_session_id: str | None = Header(default=None),
) -> UploadResponse:
    if not x_session_id:
        raise HTTPException(400, "X-Session-Id header is required")

    # Generate IDs and reserve a target path.
    attempt_id = uuid.uuid4().hex
    job_id = uuid.uuid4().hex
    settings.ensure_dirs()
    suffix = Path(video.filename or "upload.mp4").suffix or ".mp4"
    target_path = settings.uploads_dir / f"{attempt_id}{suffix}"

    # Stream upload to disk, enforcing size limit as we go.
    max_bytes = settings.upload_max_bytes
    written = 0
    async with aiofiles.open(target_path, "wb") as f:
        while True:
            chunk = await video.read(1 << 20)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                await f.close()
                target_path.unlink(missing_ok=True)
                raise HTTPException(413, f"Upload exceeds {max_bytes // (1024*1024)} MB limit")
            await f.write(chunk)

    if written == 0:
        target_path.unlink(missing_ok=True)
        raise HTTPException(400, "Empty upload")

    # Probe the file to validate duration & codec.
    try:
        info = await probe_video(target_path)
    except FFProbeError as exc:
        target_path.unlink(missing_ok=True)
        raise HTTPException(400, f"Could not read video: {exc}") from exc

    if info.duration_s > settings.upload_max_duration_s:
        target_path.unlink(missing_ok=True)
        raise HTTPException(
            400,
            f"Video is {info.duration_s:.1f}s; must be ≤ {settings.upload_max_duration_s:.0f}s",
        )
    if info.duration_s <= 0:
        target_path.unlink(missing_ok=True)
        raise HTTPException(400, "Video duration is zero")

    # Upsert session and insert attempt row.
    with db_session() as s:
        sess = s.get(SessionRow, x_session_id)
        if sess is None:
            sess = SessionRow(session_id=x_session_id)
            s.add(sess)

        # Determine label based on existing attempts for this session.
        existing_count = sum(1 for _ in sess.attempts)
        label = f"v{existing_count + 1}"

        row = AttemptRow(
            attempt_id=attempt_id,
            session_id=x_session_id,
            label=label,
            video_filename=target_path.name,
            video_duration_s=info.duration_s,
            job_id=job_id,
            status="queued",
            has_brain_video=0,
        )
        s.add(row)

    # Enqueue the job after commit.
    get_queue().submit(
        job_id=job_id,
        attempt_id=attempt_id,
        video_path=target_path,
        duration_s=info.duration_s,
    )

    return UploadResponse(job_id=job_id, attempt_id=attempt_id)
