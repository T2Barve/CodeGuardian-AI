from typing import List, TYPE_CHECKING
from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.review import ReviewJob


class PullRequest(Base, TimestampMixin):
    __tablename__ = "pull_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    github_pr_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    source_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    target_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", nullable=False)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="pull_requests")
    review_jobs: Mapped[List["ReviewJob"]] = relationship(
        "ReviewJob", back_populates="pull_request", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("repository_id", "number", name="uq_repo_pr_number"),
        Index("idx_pull_requests_repo_number", "repository_id", "number"),
    )

    def __repr__(self) -> str:
        return f"<PullRequest #{self.number}: {self.title}>"
