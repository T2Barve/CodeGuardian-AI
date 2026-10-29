from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.pull_request import PullRequest
from app.repositories.base import BaseRepository


class PullRequestRepository(BaseRepository[PullRequest]):
    def __init__(self, session: AsyncSession):
        super().__init__(PullRequest, session)

    async def get_by_github_pr_id(self, github_pr_id: int) -> Optional[PullRequest]:
        return await self.get_by(github_pr_id=github_pr_id)

    async def get_by_repo_and_number(self, repository_id: str, number: int) -> Optional[PullRequest]:
        return await self.get_by(repository_id=repository_id, number=number)

    async def get_with_repository(self, id: str) -> Optional[PullRequest]:
        stmt = (
            select(PullRequest)
            .options(selectinload(PullRequest.repository))
            .where(PullRequest.id == id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_repository(self, repository_id: str, skip: int = 0, limit: int = 100) -> Sequence[PullRequest]:
        return await self.list(skip=skip, limit=limit, repository_id=repository_id)
