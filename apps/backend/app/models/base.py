import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""
    
    # Common type mapping
    type_annotation_map = {
        Dict[str, Any]: JSON,
    }


class TimestampMixin:
    """Mixin providing created_at and updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


def generate_uuid() -> str:
    """Generates standard UUID string representation."""
    return str(uuid.uuid4())
