from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, generate_uuid

if TYPE_CHECKING:
    from app.models.review import ReviewRun


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    review_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="RUNNING", nullable=False)
    input_reference: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    output: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    review_run: Mapped["ReviewRun"] = relationship("ReviewRun", back_populates="agent_runs")

    def __repr__(self) -> str:
        return f"<AgentRun {self.agent_name} status={self.status} tokens={self.total_tokens}>"
