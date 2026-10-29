from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.policy import Policy, PolicyChunk
from app.repositories.base import BaseRepository


class PolicyRepository(BaseRepository[Policy]):
    def __init__(self, session: AsyncSession):
        super().__init__(Policy, session)

    async def get_with_chunks(self, id: str) -> Optional[Policy]:
        stmt = (
            select(Policy)
            .options(selectinload(Policy.chunks))
            .where(Policy.id == id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_name(self, name: str) -> Optional[Policy]:
        return await self.get_by(name=name)

    async def list_active(self, category: Optional[str] = None) -> Sequence[Policy]:
        stmt = select(Policy).where(Policy.active.is_(True))
        if category:
            stmt = stmt.where(Policy.category == category)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class PolicyChunkRepository(BaseRepository[PolicyChunk]):
    def __init__(self, session: AsyncSession):
        super().__init__(PolicyChunk, session)

    async def list_by_policy(self, policy_id: str) -> Sequence[PolicyChunk]:
        return await self.list(policy_id=policy_id, order_by=PolicyChunk.chunk_index)

    async def get_by_embedding_ref(self, embedding_reference: str) -> Optional[PolicyChunk]:
        return await self.get_by(embedding_reference=embedding_reference)
