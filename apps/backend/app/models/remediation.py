from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.finding import Finding
    from app.models.user import User


class RemediationAttempt(Base, TimestampMixin):
    __tablename__ = "remediation_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    finding_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    patch: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="REQUESTED", index=True, nullable=False)
    validation_result: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    finding: Mapped["Finding"] = relationship("Finding", back_populates="remediation_attempts")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="remediation_attempts")
    fix_pr: Mapped[Optional["FixPR"]] = relationship(
        "FixPR", back_populates="remediation_attempt", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<RemediationAttempt {self.id[:8]} status={self.status}>"


class FixPR(Base):
    __tablename__ = "fix_prs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    remediation_attempt_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("remediation_attempts.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    github_pr_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    remediation_attempt: Mapped["RemediationAttempt"] = relationship(
        "RemediationAttempt", back_populates="fix_pr"
    )

    def __repr__(self) -> str:
        return f"<FixPR #{self.number} ({self.status}) url={self.url}>"
