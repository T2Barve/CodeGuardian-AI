from datetime import datetime, timezone
from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.review import ReviewJob, ReviewRun
from app.models.finding import Finding
from app.repositories.base import BaseRepository


class ReviewJobRepository(BaseRepository[ReviewJob]):
    def __init__(self, session: AsyncSession):
        super().__init__(ReviewJob, session)

    async def get_with_pr(self, id: str) -> Optional[ReviewJob]:
        stmt = (
            select(ReviewJob)
            .options(selectinload(ReviewJob.pull_request))
            .where(ReviewJob.id == id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_pending(self, limit: int = 50) -> Sequence[ReviewJob]:
        return await self.list(limit=limit, status="QUEUED")

    async def mark_running(self, id: str) -> Optional[ReviewJob]:
        return await self.update(
            id, status="RUNNING", started_at=datetime.now(timezone.utc)
        )

    async def mark_completed(self, id: str) -> Optional[ReviewJob]:
        return await self.update(
            id, status="COMPLETED", completed_at=datetime.now(timezone.utc)
        )

    async def mark_failed(self, id: str, error_message: str) -> Optional[ReviewJob]:
        return await self.update(
            id,
            status="FAILED",
            completed_at=datetime.now(timezone.utc),
            error_message=error_message,
        )


class ReviewRunRepository(BaseRepository[ReviewRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(ReviewRun, session)

    async def get_by_job_id(self, review_job_id: str) -> Optional[ReviewRun]:
        return await self.get_by(review_job_id=review_job_id)

    async def get_with_full_details(self, id: str) -> Optional[ReviewRun]:
        stmt = (
            select(ReviewRun)
            .options(
                selectinload(ReviewRun.findings).selectinload(Finding.evidence),
                selectinload(ReviewRun.agent_runs),
                selectinload(ReviewRun.review_job),
            )
            .where(ReviewRun.id == id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
