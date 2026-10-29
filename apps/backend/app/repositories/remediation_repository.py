from typing import Any, Dict, Optional, Sequence
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.remediation import FixPR, RemediationAttempt
from app.repositories.base import BaseRepository


class RemediationRepository(BaseRepository[RemediationAttempt]):
    def __init__(self, session: AsyncSession):
        super().__init__(RemediationAttempt, session)

    async def get_with_fix_pr(self, id: str) -> Optional[RemediationAttempt]:
        stmt = (
            select(RemediationAttempt)
            .options(
                selectinload(RemediationAttempt.fix_pr),
                selectinload(RemediationAttempt.finding),
            )
            .where(RemediationAttempt.id == id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_finding(self, finding_id: str) -> Sequence[RemediationAttempt]:
        return await self.list(finding_id=finding_id)

    async def mark_validated(self, id: str, validation_result: Dict[str, Any]) -> Optional[RemediationAttempt]:
        return await self.update(
            id, status="VALIDATED", validation_result=validation_result
        )

    async def mark_rejected(
        self, id: str, validation_result: Dict[str, Any], error_message: str
    ) -> Optional[RemediationAttempt]:
        return await self.update(
            id,
            status="REJECTED",
            validation_result=validation_result,
            error_message=error_message,
        )


class FixPRRepository(BaseRepository[FixPR]):
    def __init__(self, session: AsyncSession):
        super().__init__(FixPR, session)

    async def get_by_remediation_id(self, remediation_attempt_id: str) -> Optional[FixPR]:
        return await self.get_by(remediation_attempt_id=remediation_attempt_id)

    async def get_by_github_pr_id(self, github_pr_id: int) -> Optional[FixPR]:
        return await self.get_by(github_pr_id=github_pr_id)
