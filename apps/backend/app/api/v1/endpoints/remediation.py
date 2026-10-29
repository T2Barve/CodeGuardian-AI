from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.database.session import get_db
from app.remediation.fix_pr import FixPRService
from app.remediation.service import RemediationService
from app.schemas.errors import ProblemDetailException
from app.schemas.remediation import (
    FixPRCreateRequest,
    FixPRResponse,
    RemediationListResponse,
    RemediationRequest,
    RemediationResponse,
)


router = APIRouter(tags=["Remediation Engine"])
remediation_service = RemediationService()


@router.post(
    "/findings/{finding_id}/remediate",
    response_model=RemediationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate and validate AI remediation patch in sandbox",
    description=(
        "Synthesizes a minimal, policy-grounded code patch for the finding "
        "and executes the strict 5-stage sandboxed validation pipeline (patch application, "
        "syntax check, scanner check, unit tests, regression check)."
    ),
)
async def remediate_finding(
    finding_id: str,
    request: Optional[RemediationRequest] = None,
    workspace_path: Optional[str] = Query(default=None, description="Optional local workspace path"),
    db: AsyncSession = Depends(get_db),
) -> RemediationResponse:
    try:
        custom_instructions = request.custom_instructions if request else None
        return await remediation_service.generate_and_validate_remediation(
            session=db,
            finding_id=finding_id,
            custom_instructions=custom_instructions,
            workspace_path=workspace_path,
        )
    except ValueError as ve:
        raise ProblemDetailException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Finding Not Found",
            detail=str(ve),
        )
    except Exception as e:
        raise ProblemDetailException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Remediation Generation Failed",
            detail=f"Failed to generate and validate patch for finding '{finding_id}': {str(e)}",
        )


@router.get(
    "/remediation/{remediation_id}",
    response_model=RemediationResponse,
    summary="Retrieve remediation attempt details and validation results",
)
async def get_remediation(
    remediation_id: str,
    db: AsyncSession = Depends(get_db),
) -> RemediationResponse:
    remediation = await remediation_service.get_remediation(db, remediation_id)
    if not remediation:
        raise ProblemDetailException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Remediation Not Found",
            detail=f"No remediation attempt found with ID '{remediation_id}'.",
        )
    return remediation


@router.get(
    "/findings/{finding_id}/remediations",
    response_model=RemediationListResponse,
    summary="List all remediation attempts for a finding",
)
async def list_finding_remediations(
    finding_id: str,
    db: AsyncSession = Depends(get_db),
) -> RemediationListResponse:
    try:
        return await remediation_service.list_remediations_for_finding(db, finding_id)
    except Exception as e:
        raise ProblemDetailException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Failed to List Remediations",
            detail=f"Could not fetch remediations for finding '{finding_id}': {str(e)}",
        )


@router.post(
    "/remediation/{remediation_id}/validate",
    response_model=RemediationResponse,
    summary="Re-execute sandboxed validation pipeline on an existing patch",
)
async def revalidate_remediation(
    remediation_id: str,
    workspace_path: Optional[str] = Query(default=None, description="Optional local workspace path"),
    db: AsyncSession = Depends(get_db),
) -> RemediationResponse:
    try:
        return await remediation_service.revalidate_remediation(
            session=db,
            remediation_id=remediation_id,
            workspace_path=workspace_path,
        )
    except ValueError as ve:
        raise ProblemDetailException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Remediation Not Found",
            detail=str(ve),
        )
    except Exception as e:
        raise ProblemDetailException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Revalidation Failed",
            detail=f"Failed to revalidate remediation '{remediation_id}': {str(e)}",
        )


@router.post(
    "/remediation/{remediation_id}/fix-pr",
    response_model=FixPRResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create automated GitHub Fix Pull Request for validated patch",
    description=(
        "Dispatches an automated branch creation and Pull Request on GitHub for a validated "
        "remediation attempt. Enforces that only patches that have passed the 5-stage validation pipeline "
        "can be submitted. Requires developer human approval to merge."
    ),
)
async def create_fix_pull_request(
    remediation_id: str,
    request: Optional[FixPRCreateRequest] = None,
    db: AsyncSession = Depends(get_db),
) -> FixPRResponse:
    fix_pr_service = FixPRService()
    req = request or FixPRCreateRequest(remediation_attempt_id=remediation_id)
    if req.remediation_attempt_id != remediation_id:
        req.remediation_attempt_id = remediation_id

    try:
        return await fix_pr_service.create_fix_pull_request(session=db, request=req)
    except ValueError as ve:
        raise ProblemDetailException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Fix PR Creation Blocked",
            detail=str(ve),
        )
    except Exception as e:
        raise ProblemDetailException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Fix PR Submission Failed",
            detail=f"Failed to submit Fix PR to GitHub: {str(e)}",
        )


@router.get(
    "/fix-prs",
    response_model=List[FixPRResponse],
    summary="List all automated Fix Pull Requests",
)
async def list_fix_prs(
    pr_status: Optional[str] = Query(None, alias="status", description="Filter by status (OPEN, MERGED, CLOSED)"),
    db: AsyncSession = Depends(get_db),
) -> List[FixPRResponse]:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.remediation import FixPR, RemediationAttempt
    from app.models.finding import Finding
    from app.models.review import ReviewRun, ReviewJob
    from app.models.pull_request import PullRequest
    from app.models.repository import Repository

    stmt = (
        select(FixPR)
        .options(
            selectinload(FixPR.remediation_attempt)
            .selectinload(RemediationAttempt.finding)
            .selectinload(Finding.review_run)
            .selectinload(ReviewRun.review_job)
            .selectinload(ReviewJob.pull_request)
            .selectinload(PullRequest.repository)
        )
        .order_by(FixPR.created_at.desc())
    )
    if pr_status:
        stmt = stmt.where(FixPR.status == pr_status.upper())

    res = await db.execute(stmt)
    records = res.scalars().all()

    items: List[FixPRResponse] = []
    for p in records:
        attempt = p.remediation_attempt
        finding = attempt.finding if attempt else None
        repo_name = "unknown/repository"
        base_branch = "main"

        if finding and finding.review_run and finding.review_run.review_job:
            pr = finding.review_run.review_job.pull_request
            if pr and pr.repository:
                repo_name = f"{pr.repository.owner}/{pr.repository.name}"
                base_branch = pr.target_branch or pr.repository.default_branch

        items.append(
            FixPRResponse(
                id=p.id,
                remediation_attempt_id=p.remediation_attempt_id,
                finding_id=attempt.finding_id if attempt else "",
                repo_name=repo_name,
                github_pr_id=p.github_pr_id,
                number=p.number,
                url=p.url,
                branch_name=f"codeguardian/fix-{attempt.finding_id[:8]}" if attempt else "codeguardian/fix",
                base_branch=base_branch,
                status=p.status,
                created_at=p.created_at,
            )
        )

    return items


@router.get(
    "/fix-prs/{fix_pr_id}",
    response_model=FixPRResponse,
    summary="Retrieve Fix Pull Request details and status",
)
async def get_fix_pr(
    fix_pr_id: str,
    db: AsyncSession = Depends(get_db),
) -> FixPRResponse:
    fix_pr_service = FixPRService()
    fix_pr = await fix_pr_service.get_fix_pr(session=db, fix_pr_id=fix_pr_id)
    if not fix_pr:
        raise ProblemDetailException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Fix PR Not Found",
            detail=f"No Fix PR found with ID '{fix_pr_id}'.",
        )
    return fix_pr


