from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import BigInteger, Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.pull_request import PullRequest


class Repository(Base, TimestampMixin):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    github_repo_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    pull_requests: Mapped[List["PullRequest"]] = relationship(
        "PullRequest", back_populates="repository", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_repositories_owner_name", "owner", "name"),
    )

    def __repr__(self) -> str:
        return f"<Repository {self.owner}/{self.name}>"
