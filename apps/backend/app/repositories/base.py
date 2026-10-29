from typing import Any, Generic, List, Optional, Sequence, Type, TypeVar
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic repository providing standardized async CRUD operations."""

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def create(self, **kwargs: Any) -> ModelType:
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def get(self, id: str) -> Optional[ModelType]:
        result = await self.session.execute(select(self.model).where(self.model.id == id))
        return result.scalars().first()

    async def get_by(self, **kwargs: Any) -> Optional[ModelType]:
        stmt = select(self.model).filter_by(**kwargs)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Any = None,
        **filters: Any
    ) -> Sequence[ModelType]:
        stmt = select(self.model).filter_by(**filters)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(self, **filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model).filter_by(**filters)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def update(self, id: str, **kwargs: Any) -> Optional[ModelType]:
        instance = await self.get(id)
        if not instance:
            return None
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, id: str) -> bool:
        instance = await self.get(id)
        if not instance:
            return False
        await self.session.delete(instance)
        await self.session.flush()
        return True
