"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


SUB_SCORE_NAMES = ("reward", "emotion", "attention", "novelty", "social_relevance")

JobStatus = Literal["queued", "preprocessing", "inferring", "scoring", "rendering", "done", "error"]


class SubScores(BaseModel):
    reward: float
    emotion: float
    attention: float
    novelty: float
    social_relevance: float


class TimelinePoint(BaseModel):
    t: float
    reward: float
    emotion: float
    attention: float
    novelty: float
    social_relevance: float


class UploadResponse(BaseModel):
    job_id: str
    attempt_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    stage_label: str
    attempt_id: str | None = None
    error_message: str | None = None


class AttemptSummary(BaseModel):
    attempt_id: str
    label: str
    uploaded_at: datetime
    status: str
    headline_score: int | None = None
    video_duration_s: float
    has_brain_video: bool = False


class AttemptResult(BaseModel):
    attempt_id: str
    label: str
    uploaded_at: datetime
    status: str
    video_filename: str
    video_duration_s: float
    headline_score: int | None
    sub_scores: SubScores | None
    timeline: list[TimelinePoint] | None
    has_brain_video: bool = False
    brain_frame_count: int = 0
    error_message: str | None = None
