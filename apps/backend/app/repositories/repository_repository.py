from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.repository import Repository
from app.repositories.base import BaseRepository


class RepositoryRepository(BaseRepository[Repository]):
    def __init__(self, session: AsyncSession):
        super().__init__(Repository, session)

    async def get_by_github_repo_id(self, github_repo_id: int) -> Optional[Repository]:
        return await self.get_by(github_repo_id=github_repo_id)

    async def get_by_owner_and_name(self, owner: str, name: str) -> Optional[Repository]:
        return await self.get_by(owner=owner, name=name)

    async def list_active(self) -> Sequence[Repository]:
        return await self.list(is_active=True)
