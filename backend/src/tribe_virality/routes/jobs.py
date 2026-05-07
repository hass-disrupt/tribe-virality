"""GET /api/jobs/{job_id}."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..jobs import get_queue
from ..schemas import JobStatusResponse


router = APIRouter(prefix="/api")


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str) -> JobStatusResponse:
    state = get_queue().get_state(job_id)
    if state is None:
        raise HTTPException(404, "job not found")
    return JobStatusResponse(
        job_id=state.job_id,
        status=state.status,  # type: ignore[arg-type]
        progress=state.progress,
        stage_label=state.stage_label,
        attempt_id=state.attempt_id,
        error_message=state.error_message,
    )
