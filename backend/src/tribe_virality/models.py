"""SQLAlchemy ORM models for Sessions and Attempts."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class SessionRow(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    attempts: Mapped[list["AttemptRow"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class AttemptRow(Base):
    __tablename__ = "attempts"

    attempt_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), index=True)
    label: Mapped[str] = mapped_column(String)
    video_filename: Mapped[str] = mapped_column(String)
    video_duration_s: Mapped[float] = mapped_column(Float)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    job_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="queued")

    headline_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sub_scores_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeline_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_brain_video: Mapped[int] = mapped_column(Integer, default=0)
    brain_frame_count: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped[SessionRow] = relationship(back_populates="attempts")
