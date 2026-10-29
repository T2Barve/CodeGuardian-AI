from typing import Any, Dict, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    def __init__(self, session: AsyncSession):
        super().__init__(AuditLog, session)

    async def record(
        self,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: str,
        metadata_payload: Dict[str, Any] | None = None,
    ) -> AuditLog:
        return await self.create(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_payload=metadata_payload or {},
        )

    async def list_by_resource(
        self, resource_type: str, resource_id: str, limit: int = 50
    ) -> Sequence[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.resource_type == resource_type, AuditLog.resource_id == resource_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_recent(self, limit: int = 100) -> Sequence[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()
