import time
from typing import Any, Dict, List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import build_review_graph
from app.agents.state import ReviewState, ReviewStateInput
from app.repositories.agent_repository import AgentRunRepository
from app.repositories.audit_repository import AuditRepository
from app.services.llm.base import BaseLLMProvider
from app.services.llm.factory import get_llm_provider

logger = structlog.get_logger(__name__)


class SupervisorService:
    """
    High-level Service for orchestrating LangGraph Multi-Agent Reviews.
    
    Adheres to Rule 15 (Supervisor Agent) & Rule 35 (Fault Tolerance).
    Manages LangGraph invocation, state reduction, agent execution logging,
    and PostgreSQL persistence of AgentRun telemetry.
    """

    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self.llm_provider = llm_provider or get_llm_provider()
        self.graph = build_review_graph(llm_provider=self.llm_provider)

    async def run_review(
        self,
        input_data: ReviewStateInput,
        session: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Executes the compiled multi-agent LangGraph workflow and optionally persists telemetry.
        """
        start_time = time.perf_counter()
        logger.info(
            "Initiating LangGraph multi-agent review",
            repo_name=input_data.repo_name,
            pr_number=input_data.pr_number,
            commit_sha=input_data.commit_sha[:8],
            files_count=len(input_data.changed_files),
        )

        initial_state: ReviewState = {
            "repo_owner": input_data.repo_owner,
            "repo_name": input_data.repo_name,
            "pr_number": input_data.pr_number,
            "commit_sha": input_data.commit_sha,
            "changed_files": input_data.changed_files,
            "diff_content": input_data.diff_content,
            "workspace_path": input_data.workspace_path,
            "review_run_id": input_data.review_run_id,
            "normalized_scan_results": input_data.normalized_scan_results,
            "retrieved_policies": input_data.retrieved_policies,
            "ast_metadata": input_data.ast_metadata,
            "active_agents": [],
            "file_partitioning": {},
            "supervisor_rationale": "",
            "security_findings": [],
            "quality_findings": [],
            "testing_findings": [],
            "documentation_findings": [],
            "dependency_findings": [],
            "agent_errors": {},
            "token_usage": {},
            "agent_telemetry": {},
            "correlated_findings": [],
            "risk_assessment": None,
            "summary_report": "",
        }

        # Invoke the LangGraph workflow asynchronously
        final_state: Dict[str, Any] = await self.graph.ainvoke(initial_state)
        total_duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Persist AgentRun telemetry if session and review_run_id are present
        if session and input_data.review_run_id:
            await self._persist_agent_runs(
                session=session,
                review_run_id=input_data.review_run_id,
                state=final_state,
            )

        logger.info(
            "LangGraph multi-agent review completed",
            duration_ms=total_duration_ms,
            active_agents=final_state.get("active_agents", []),
            findings_count=len(final_state.get("correlated_findings", [])),
            risk_score=(final_state.get("risk_assessment") or {}).get("overall_score", 0.0),
        )

        return final_state

    async def _persist_agent_runs(
        self,
        session: AsyncSession,
        review_run_id: str,
        state: Dict[str, Any],
    ) -> None:
        """Persists individual AgentRun database records for audit and dashboard inspection."""
        agent_repo = AgentRunRepository(session)
        audit_repo = AuditRepository(session)
        telemetry = state.get("agent_telemetry", {})
        token_usage = state.get("token_usage", {})
        agent_errors = state.get("agent_errors", {})

        for agent_name, agent_data in telemetry.items():
            duration_ms = agent_data.get("duration_ms", 0)
            tokens = token_usage.get(agent_name, 0)
            err = agent_errors.get(agent_name)
            status = "FAILED" if err else agent_data.get("status", "COMPLETED")

            await agent_repo.record_run(
                review_run_id=review_run_id,
                agent_name=agent_name,
                status=status,
                input_reference={
                    "files": state.get("file_partitioning", {}).get(agent_name, []),
                },
                output=agent_data,
                duration_ms=duration_ms,
                prompt_tokens=int(tokens * 0.7),
                completion_tokens=int(tokens * 0.3),
                total_tokens=tokens,
                error=err,
            )

        # Record high-level audit trail
        await audit_repo.record(
            actor="codeguardian-supervisor",
            action="MULTI_AGENT_REVIEW_COMPLETED",
            resource_type="review_run",
            resource_id=review_run_id,
            metadata_payload={
                "active_agents": state.get("active_agents", []),
                "findings_count": len(state.get("correlated_findings", [])),
                "risk_score": (state.get("risk_assessment") or {}).get("overall_score", 0.0),
            },
        )
        await session.commit()
