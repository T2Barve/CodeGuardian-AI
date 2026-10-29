from datetime import datetime, timezone
from typing import Any, Dict, List, TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid


class Policy(Base, TimestampMixin):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    chunks: Mapped[List["PolicyChunk"]] = relationship(
        "PolicyChunk", back_populates="policy", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Policy {self.name} ({self.category} v{self.version})>"


class PolicyChunk(Base):
    __tablename__ = "policy_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    policy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    policy: Mapped["Policy"] = relationship("Policy", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<PolicyChunk {self.policy_id[:8]} index={self.chunk_index}>"
