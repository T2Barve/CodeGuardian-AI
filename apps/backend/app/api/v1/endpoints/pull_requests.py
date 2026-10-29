from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.session import get_db
from app.models.finding import Finding
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob, ReviewRun
from app.repositories.audit_repository import AuditRepository
from app.repositories.review_repository import ReviewJobRepository
from app.schemas.errors import ProblemDetailException
from app.schemas.pull_request import (
    PullRequestAnalyzeRequest,
    PullRequestAnalyzeResponse,
    PullRequestListResponse,
    PullRequestRead,
)
from app.schemas.queue import ReviewJobPayload
from app.utils.logging import get_logger
from app.workers.queue import get_review_queue

logger = get_logger("codeguardian.api.pull_requests")
router = APIRouter(prefix="/pull-requests", tags=["Pull Requests"])


@router.get(
    "",
    response_model=PullRequestListResponse,
    summary="List all tracked pull requests across repositories",
)
async def list_pull_requests(
    repository_id: Optional[str] = Query(None, description="Filter by repository ID"),
    pr_status: Optional[str] = Query(None, alias="status", description="Filter by status (OPEN, CLOSED, MERGED)"),
    search: Optional[str] = Query(None, description="Search by title, author, or PR number"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> PullRequestListResponse:
    stmt = (
        select(PullRequest)
        .options(
            selectinload(PullRequest.repository),
            selectinload(PullRequest.review_jobs)
            .selectinload(ReviewJob.review_run)
            .selectinload(ReviewRun.findings),
        )
        .order_by(PullRequest.updated_at.desc())
    )

    if repository_id:
        stmt = stmt.where(PullRequest.repository_id == repository_id)

    if pr_status:
        stmt = stmt.where(PullRequest.status == pr_status.upper())

    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            or_(
                PullRequest.title.ilike(search_term),
                PullRequest.author.ilike(search_term),
            )
        )

    # Count total
    count_stmt = select(func.count(PullRequest.id))
    if repository_id:
        count_stmt = count_stmt.where(PullRequest.repository_id == repository_id)
    if pr_status:
        count_stmt = count_stmt.where(PullRequest.status == pr_status.upper())
    if search:
        search_term = f"%{search}%"
        count_stmt = count_stmt.where(
            or_(
                PullRequest.title.ilike(search_term),
                PullRequest.author.ilike(search_term),
            )
        )

    total_count = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    prs = result.scalars().all()

    items: List[PullRequestRead] = []
    for pr in prs:
        repo = pr.repository
        repo_name = repo.name if repo else "unknown"
        repo_owner = repo.owner if repo else "unknown"

        # Find latest completed review run
        latest_run = None
        for job in sorted(pr.review_jobs, key=lambda j: j.queued_at, reverse=True):
            if job.review_run:
                latest_run = job.review_run
                break

        crit_count = 0
        high_count = 0
        total_f = 0
        risk_score = None
        risk_grade = None
        risk_level = "LOW"
        is_mergeable = True
        last_analyzed = None

        if latest_run:
            risk_score = latest_run.risk_score
            risk_grade = latest_run.risk_grade
            last_analyzed = latest_run.completed_at or latest_run.started_at
            crit_count = sum(1 for f in latest_run.findings if f.severity.upper() == "CRITICAL")
            high_count = sum(1 for f in latest_run.findings if f.severity.upper() == "HIGH")
            total_f = len(latest_run.findings)

            config = latest_run.configuration or {}
            risk_assessment = config.get("risk_assessment") or {}
            if risk_assessment:
                risk_level = risk_assessment.get("level", "LOW")
                is_mergeable = bool(risk_assessment.get("is_mergeable", True))

        items.append(
            PullRequestRead(
                id=pr.id,
                github_pr_id=pr.github_pr_id,
                repository_id=pr.repository_id,
                repo_name=repo_name,
                repo_owner=repo_owner,
                repo_full_name=f"{repo_owner}/{repo_name}",
                number=pr.number,
                title=pr.title,
                author=pr.author,
                source_branch=pr.source_branch,
                target_branch=pr.target_branch,
                commit_sha=pr.commit_sha,
                status=pr.status,
                latest_review_run_id=latest_run.id if latest_run else None,
                latest_risk_score=risk_score,
                latest_risk_grade=risk_grade,
                latest_risk_level=risk_level,
                is_mergeable=is_mergeable,
                critical_count=crit_count,
                high_count=high_count,
                total_findings=total_f,
                last_analyzed_at=last_analyzed,
                created_at=pr.created_at,
                updated_at=pr.updated_at,
            )
        )

    return PullRequestListResponse(total=total_count, items=items)


@router.get(
    "/{pull_request_id}",
    response_model=PullRequestRead,
    summary="Get detailed information for a single pull request",
)
async def get_pull_request(
    pull_request_id: str,
    db: AsyncSession = Depends(get_db),
) -> PullRequestRead:
    stmt = (
        select(PullRequest)
        .options(
            selectinload(PullRequest.repository),
            selectinload(PullRequest.review_jobs)
            .selectinload(ReviewJob.review_run)
            .selectinload(ReviewRun.findings),
        )
        .where(PullRequest.id == pull_request_id)
    )
    result = await db.execute(stmt)
    pr = result.scalars().first()

    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pull request '{pull_request_id}' not found.",
        )

    repo = pr.repository
    repo_name = repo.name if repo else "unknown"
    repo_owner = repo.owner if repo else "unknown"

    latest_run = None
    for job in sorted(pr.review_jobs, key=lambda j: j.queued_at, reverse=True):
        if job.review_run:
            latest_run = job.review_run
            break

    crit_count = 0
    high_count = 0
    total_f = 0
    risk_score = None
    risk_grade = None
    risk_level = "LOW"
    is_mergeable = True
    last_analyzed = None

    if latest_run:
        risk_score = latest_run.risk_score
        risk_grade = latest_run.risk_grade
        last_analyzed = latest_run.completed_at or latest_run.started_at
        crit_count = sum(1 for f in latest_run.findings if f.severity.upper() == "CRITICAL")
        high_count = sum(1 for f in latest_run.findings if f.severity.upper() == "HIGH")
        total_f = len(latest_run.findings)

        config = latest_run.configuration or {}
        risk_assessment = config.get("risk_assessment") or {}
        if risk_assessment:
            risk_level = risk_assessment.get("level", "LOW")
            is_mergeable = bool(risk_assessment.get("is_mergeable", True))

    return PullRequestRead(
        id=pr.id,
        github_pr_id=pr.github_pr_id,
        repository_id=pr.repository_id,
        repo_name=repo_name,
        repo_owner=repo_owner,
        repo_full_name=f"{repo_owner}/{repo_name}",
        number=pr.number,
        title=pr.title,
        author=pr.author,
        source_branch=pr.source_branch,
        target_branch=pr.target_branch,
        commit_sha=pr.commit_sha,
        status=pr.status,
        latest_review_run_id=latest_run.id if latest_run else None,
        latest_risk_score=risk_score,
        latest_risk_grade=risk_grade,
        latest_risk_level=risk_level,
        is_mergeable=is_mergeable,
        critical_count=crit_count,
        high_count=high_count,
        total_findings=total_f,
        last_analyzed_at=last_analyzed,
        created_at=pr.created_at,
        updated_at=pr.updated_at,
    )


@router.post(
    "/{pull_request_id}/analyze",
    response_model=PullRequestAnalyzeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger immediate automated code review and multi-agent analysis on a pull request",
)
async def trigger_pr_analysis(
    pull_request_id: str,
    payload: PullRequestAnalyzeRequest = PullRequestAnalyzeRequest(),
    db: AsyncSession = Depends(get_db),
) -> PullRequestAnalyzeResponse:
    stmt = (
        select(PullRequest)
        .options(selectinload(PullRequest.repository))
        .where(PullRequest.id == pull_request_id)
    )
    result = await db.execute(stmt)
    pr = result.scalars().first()

    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pull request '{pull_request_id}' not found.",
        )

    repo = pr.repository
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository association missing for pull request.",
        )

    # 1. Create ReviewJob entity (status=QUEUED)
    job_repo = ReviewJobRepository(db)
    job = await job_repo.create(
        pull_request_id=pr.id,
        status="QUEUED",
    )

    # 2. Record audit log
    audit_repo = AuditRepository(db)
    await audit_repo.record(
        actor="dashboard-user",
        action="REVIEW_JOB_MANUAL_TRIGGER",
        resource_type="review_job",
        resource_id=job.id,
        metadata_payload={
            "pr_number": pr.number,
            "repo": f"{repo.owner}/{repo.name}",
            "commit_sha": pr.commit_sha,
            "action": payload.action,
        },
    )

    # 3. Enqueue job to background queue
    queue = get_review_queue()
    job_payload = ReviewJobPayload(
        job_id=job.id,
        pull_request_id=pr.id,
        repo_name=repo.name,
        repo_owner=repo.owner,
        pr_number=pr.number,
        commit_sha=pr.commit_sha,
        action=payload.action or "manual",
        metadata={
            "repo_url": repo.url,
        },
    )
    try:
        enqueued = await queue.enqueue_review(job_payload)
        if not enqueued:
            logger.info("Job was already in queue or deduped", extra={"job_id": job.id})
    except Exception as exc:
        logger.error(f"Failed to enqueue review job: {exc}", extra={"job_id": job.id})
        await job_repo.update(job.id, status="FAILED")
        await db.commit()
        from app.schemas.errors import ProblemDetailException
        raise ProblemDetailException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            title="Analysis Service Unavailable",
            detail=f"Unable to dispatch review job to the execution queue: {str(exc)}",
        )

    logger.info(
        "Enqueued automated review job via manual trigger",
        extra={
            "job_id": job.id,
            "repo": f"{repo.owner}/{repo.name}",
            "pr_number": pr.number,
        },
    )

    return PullRequestAnalyzeResponse(
        job_id=job.id,
        pull_request_id=pr.id,
        status="QUEUED",
        message=f"Review job for PR #{pr.number} ({repo.owner}/{repo.name}) enqueued successfully.",
    )
