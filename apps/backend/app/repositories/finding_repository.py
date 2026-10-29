from typing import Dict, Optional, Sequence
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.finding import Finding, FindingEvidence
from app.repositories.base import BaseRepository


class FindingRepository(BaseRepository[Finding]):
    def __init__(self, session: AsyncSession):
        super().__init__(Finding, session)

    async def get_with_evidence(self, id: str) -> Optional[Finding]:
        stmt = (
            select(Finding)
            .options(selectinload(Finding.evidence))
            .where(Finding.id == id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_fingerprint(self, review_run_id: str, fingerprint: str) -> Optional[Finding]:
        return await self.get_by(review_run_id=review_run_id, fingerprint=fingerprint)

    async def list_by_review_run(
        self,
        review_run_id: str,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Sequence[Finding]:
        stmt = select(Finding).options(selectinload(Finding.evidence)).where(Finding.review_run_id == review_run_id)
        if category:
            stmt = stmt.where(Finding.category == category)
        if severity:
            stmt = stmt.where(Finding.severity == severity)
        if status:
            stmt = stmt.where(Finding.status == status)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_severity_counts(self, review_run_id: str) -> Dict[str, int]:
        stmt = (
            select(Finding.severity, func.count(Finding.id))
            .where(Finding.review_run_id == review_run_id)
            .group_by(Finding.severity)
        )
        result = await self.session.execute(stmt)
        return {severity: count for severity, count in result.all()}


class FindingEvidenceRepository(BaseRepository[FindingEvidence]):
    def __init__(self, session: AsyncSession):
        super().__init__(FindingEvidence, session)

    async def list_by_finding(self, finding_id: str) -> Sequence[FindingEvidence]:
        return await self.list(finding_id=finding_id)
