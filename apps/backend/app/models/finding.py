from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, generate_uuid

if TYPE_CHECKING:
    from app.models.review import ReviewRun
    from app.models.remediation import RemediationAttempt


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    review_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fingerprint: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True, nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    line_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    line_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    impact: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    policy_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    review_run: Mapped["ReviewRun"] = relationship("ReviewRun", back_populates="findings")
    evidence: Mapped[List["FindingEvidence"]] = relationship(
        "FindingEvidence", back_populates="finding", cascade="all, delete-orphan"
    )
    remediation_attempts: Mapped[List["RemediationAttempt"]] = relationship(
        "RemediationAttempt", back_populates="finding", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Finding [{self.severity}] {self.title[:30]} ({self.file_path})>"


class FindingEvidence(Base):
    __tablename__ = "finding_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    finding_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # SCANNER, AGENT
    tool: Mapped[str] = mapped_column(String(64), nullable=False)    # semgrep, bandit, gitleaks, etc.
    rule_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    raw_message: Mapped[str] = mapped_column(Text, nullable=False)
    code_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    finding: Mapped["Finding"] = relationship("Finding", back_populates="evidence")

    def __repr__(self) -> str:
        return f"<FindingEvidence {self.source}:{self.tool}:{self.rule_id}>"
