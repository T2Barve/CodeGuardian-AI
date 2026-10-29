from typing import Any, Dict, List, Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.service import SupervisorService
from app.agents.state import ReviewStateInput
from app.agents.supervisor import SupervisorAgent, classify_files_for_review
from app.config.settings import settings
from app.database.session import get_db
from app.models.agent import AgentRun
from app.models.review import ReviewJob
from app.repositories.agent_repository import AgentRunRepository
from app.repositories.review_repository import ReviewRunRepository
from app.schemas.agent import (
    AgentRunResponse,
    AgentRunsListResponse,
    FileClassificationRequest,
    FileClassificationResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


class AgentStatusInfo(BaseModel):
    name: str
    display_name: str
    role: str
    status: str  # IDLE, ACTIVE, COMPLETED, FAILED
    total_runs: int = 0
    avg_duration_ms: int = 0
    total_tokens: int = 0
    discovered_findings: int = 0
    provider: str
    model: str


class MultiAgentControlCenterResponse(BaseModel):
    is_orchestration_active: bool
    active_jobs_count: int
    total_agent_executions: int
    total_tokens_consumed: int
    agents: List[AgentStatusInfo]


@router.get(
    "/agents/status",
    response_model=MultiAgentControlCenterResponse,
    summary="Get live Multi-Agent Orchestration Fabric status and execution telemetry",
)
async def get_multi_agent_status(
    db: AsyncSession = Depends(get_db),
) -> MultiAgentControlCenterResponse:
    # Check if any review job is actively running
    running_jobs_stmt = select(func.count(ReviewJob.id)).where(ReviewJob.status == "RUNNING")
    running_jobs = (await db.execute(running_jobs_stmt)).scalar() or 0
    is_active = running_jobs > 0

    # Query agent runs by agent_name
    agent_defs = [
        ("SupervisorAgent", "LangGraph Supervisor", "Evaluates PR metadata, orchestrates routing to specialists, synthesizes final consensus"),
        ("SecurityAgent", "Security Agent", "Analyzes taint paths, OWASP Top 10, CWE-89 SQLi, CWE-78 command execution, hardcoded keys"),
        ("CodeQualityAgent", "Code Quality Agent", "Detects anti-patterns, cyclomatic complexity spikes, code smells, maintainability index"),
        ("TestingAgent", "Testing & Reliability Agent", "Verifies test coverage delta, scaffolding gaps, error boundary assertions, mocks"),
        ("DocSynthesisAgent", "Documentation Agent", "Audits docstrings, API schema drift, README sync, and changelog compliance"),
        ("DependencyAgent", "Dependency Graph Agent", "Checks package manifest security, wildcard versions, CVE vulnerability databases"),
    ]

    agent_status_list: List[AgentStatusInfo] = []
    total_runs_all = 0
    total_tokens_all = 0

    for name, display_name, role in agent_defs:
        stats_stmt = (
            select(
                func.count(AgentRun.id),
                func.coalesce(func.avg(AgentRun.duration_ms), 0),
                func.coalesce(func.sum(AgentRun.total_tokens), 0),
            )
            .where(AgentRun.agent_name.ilike(f"%{name[:8]}%"))
        )
        res = await db.execute(stats_stmt)
        row = res.first()
        runs_count = row[0] if row else 0
        avg_dur = int(row[1]) if row else 0
        tokens = int(row[2]) if row else 0

        total_runs_all += runs_count
        total_tokens_all += tokens

        agent_status_list.append(
            AgentStatusInfo(
                name=name,
                display_name=display_name,
                role=role,
                status="ACTIVE" if is_active else ("COMPLETED" if runs_count > 0 else "IDLE"),
                total_runs=runs_count,
                avg_duration_ms=avg_dur,
                total_tokens=tokens,
                discovered_findings=0,
                provider=settings.LLM_PROVIDER,
                model=settings.LLM_MODEL_NAME,
            )
        )

    return MultiAgentControlCenterResponse(
        is_orchestration_active=is_active,
        active_jobs_count=running_jobs,
        total_agent_executions=total_runs_all,
        total_tokens_consumed=total_tokens_all,
        agents=agent_status_list,
    )



@router.get(
    "/reviews/{review_run_id}/agents",
    response_model=AgentRunsListResponse,
    summary="List all agent executions for a review",
)
async def list_review_agents(
    review_run_id: str,
    db: AsyncSession = Depends(get_db),
) -> AgentRunsListResponse:
    """Retrieves execution telemetry and outputs for all agents that ran for a review run."""
    run_repo = ReviewRunRepository(db)
    review_run = await run_repo.get(review_run_id)
    if not review_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ReviewRun '{review_run_id}' not found.",
        )

    agent_repo = AgentRunRepository(db)
    agent_runs = await agent_repo.get_by_review_run_id(review_run_id)

    return AgentRunsListResponse(
        review_run_id=review_run_id,
        total_agents=len(agent_runs),
        agents=[
            AgentRunResponse(
                id=a.id,
                review_run_id=a.review_run_id,
                agent_name=a.agent_name,
                status=a.status,
                input_reference=a.input_reference,
                output=a.output,
                duration_ms=a.duration_ms,
                prompt_tokens=a.prompt_tokens,
                completion_tokens=a.completion_tokens,
                total_tokens=a.total_tokens,
                estimated_cost=a.estimated_cost,
                error=a.error,
                created_at=a.created_at,
            )
            for a in agent_runs
        ],
    )


@router.post(
    "/agents/classify",
    response_model=FileClassificationResponse,
    summary="Preview file classification and specialist routing",
)
async def classify_pr_files(
    payload: FileClassificationRequest,
) -> FileClassificationResponse:
    """Evaluates changed files and returns activated specialist agents and file partitions."""
    supervisor = SupervisorAgent()
    decision = await supervisor.evaluate_and_route(
        repo_name=payload.repo_name or "unknown",
        pr_number=payload.pr_number or 0,
        changed_files=payload.changed_files,
    )
    return FileClassificationResponse(
        active_agents=decision.active_agents,
        file_partitioning=decision.file_partitioning,
        rationale=decision.rationale,
    )


@router.post(
    "/reviews/{review_run_id}/agents/run",
    response_model=Dict[str, Any],
    summary="Trigger LangGraph multi-agent execution on a review",
)
async def run_review_agents(
    review_run_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Manually triggers or re-runs the LangGraph review graph for a given review run."""
    run_repo = ReviewRunRepository(db)
    review_run = await run_repo.get(review_run_id)
    if not review_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ReviewRun '{review_run_id}' not found.",
        )

    config = review_run.configuration or {}
    changed_files = config.get("changed_files", ["src/main.py"])
    repo_name = config.get("repo_name", "unknown")
    pr_number = config.get("pr_number", 1)
    commit_sha = config.get("commit_sha", "HEAD")

    service = SupervisorService()
    input_data = ReviewStateInput(
        repo_owner=repo_name.split("/")[0] if "/" in repo_name else "owner",
        repo_name=repo_name,
        pr_number=pr_number,
        commit_sha=commit_sha,
        changed_files=changed_files,
        diff_content=config.get("diff_content", ""),
        workspace_path=config.get("workspace_path"),
        review_run_id=review_run_id,
        normalized_scan_results=config.get("normalized_scan_results", []),
    )

    final_state = await service.run_review(input_data=input_data, session=db)
    return {
        "review_run_id": review_run_id,
        "active_agents": final_state.get("active_agents", []),
        "supervisor_rationale": final_state.get("supervisor_rationale", ""),
        "findings_count": len(final_state.get("correlated_findings", [])),
        "risk_assessment": final_state.get("risk_assessment"),
        "summary_report": final_state.get("summary_report", ""),
    }
