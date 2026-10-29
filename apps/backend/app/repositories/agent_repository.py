from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.agent import AgentRun
from app.repositories.base import BaseRepository


class AgentRunRepository(BaseRepository[AgentRun]):
    """Repository handling CRUD operations and queries for AgentRun records."""

    def __init__(self, session: AsyncSession):
        super().__init__(AgentRun, session)

    async def get_by_review_run_id(self, review_run_id: str) -> List[AgentRun]:
        """Retrieves all agent execution records for a specified review run."""
        query = (
            select(AgentRun)
            .where(AgentRun.review_run_id == review_run_id)
            .order_by(AgentRun.created_at.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def record_run(
        self,
        review_run_id: str,
        agent_name: str,
        status: str,
        input_reference: Optional[Dict[str, Any]] = None,
        output: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        estimated_cost: float = 0.0,
        error: Optional[str] = None,
    ) -> AgentRun:
        """Creates and persists an AgentRun record with execution telemetry."""
        agent_run = AgentRun(
            review_run_id=review_run_id,
            agent_name=agent_name,
            status=status,
            input_reference=input_reference,
            output=output,
            duration_ms=duration_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            error=error,
        )
        self.session.add(agent_run)
        await self.session.flush()
        return agent_run
