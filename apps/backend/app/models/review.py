from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, generate_uuid

if TYPE_CHECKING:
    from app.models.pull_request import PullRequest
    from app.models.finding import Finding
    from app.models.agent import AgentRun


class ReviewJob(Base):
    __tablename__ = "review_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    pull_request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True, nullable=False)
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    pull_request: Mapped["PullRequest"] = relationship("PullRequest", back_populates="review_jobs")
    review_run: Mapped[Optional["ReviewRun"]] = relationship(
        "ReviewRun", back_populates="review_job", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ReviewJob {self.id[:8]} status={self.status}>"


class ReviewRun(Base):
    __tablename__ = "review_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    review_job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("review_jobs.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    configuration: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="RUNNING", nullable=False)
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_grade: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    review_job: Mapped["ReviewJob"] = relationship("ReviewJob", back_populates="review_run")
    findings: Mapped[List["Finding"]] = relationship(
        "Finding", back_populates="review_run", cascade="all, delete-orphan"
    )
    agent_runs: Mapped[List["AgentRun"]] = relationship(
        "AgentRun", back_populates="review_run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ReviewRun {self.id[:8]} grade={self.risk_grade} score={self.risk_score}>"
