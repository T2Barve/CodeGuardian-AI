from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.remediation import RemediationAttempt


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    github_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, index=True, nullable=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="DEVELOPER", nullable=False)

    # Relationships
    remediation_attempts: Mapped[List["RemediationAttempt"]] = relationship(
        "RemediationAttempt", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.username} (role={self.role})>"
