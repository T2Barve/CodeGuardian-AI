from datetime import datetime, timezone
from typing import Any, Dict
from sqlalchemy import DateTime, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, generate_uuid


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    actor: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    __table_args__ = (
        Index("idx_audit_logs_resource", "resource_type", "resource_id"),
        Index("idx_audit_logs_timestamp", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.actor} -> {self.action} on {self.resource_type}:{self.resource_id}>"
