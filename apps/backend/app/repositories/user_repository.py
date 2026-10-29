from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_github_id(self, github_id: int) -> Optional[User]:
        return await self.get_by(github_id=github_id)

    async def get_by_username(self, username: str) -> Optional[User]:
        return await self.get_by(username=username)
