from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.audit import AuditLog

router = APIRouter(prefix="/audit", tags=["Audit & Compliance"])


class AuditLogRead(BaseModel):
    id: str
    actor: str
    action: str
    resource_type: str
    resource_id: str
    metadata_payload: Dict[str, Any]
    timestamp: datetime


class AuditLogListResponse(BaseModel):
    total: int
    items: List[AuditLogRead]


@router.get(
    "/logs",
    response_model=AuditLogListResponse,
    summary="List immutable compliance and execution audit trail logs",
)
async def list_audit_logs(
    resource_type: Optional[str] = Query(None, description="Filter by resource type (repository, review_job, finding)"),
    action: Optional[str] = Query(None, description="Filter by action name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    stmt = select(AuditLog).order_by(AuditLog.timestamp.desc())
    count_stmt = select(func.count(AuditLog.id))

    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
        count_stmt = count_stmt.where(AuditLog.resource_type == resource_type)

    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    records = result.scalars().all()

    items = [
        AuditLogRead(
            id=r.id,
            actor=r.actor,
            action=r.action,
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            metadata_payload=r.metadata_payload or {},
            timestamp=r.timestamp,
        )
        for r in records
    ]


    return AuditLogListResponse(total=total, items=items)
