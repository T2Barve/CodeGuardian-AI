from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.session import get_db
from app.findings.service import FindingService
from app.localization.service import MultilingualExplanationService
from app.models.finding import Finding, FindingEvidence
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob, ReviewRun
from app.repositories.finding_repository import FindingRepository
from app.repositories.review_repository import ReviewRunRepository
from app.schemas.finding import (
    FindingEvidenceRead,
    FindingListResponse,
    FindingRead,
    FindingStatusUpdateRequest,
)
from app.schemas.localization import (
    FindingExplanationRequest,
    FindingExplanationResponse,
    SupportedLanguage,
)
from app.voice.service import AIVoiceService

router = APIRouter()
explanation_service = MultilingualExplanationService()
voice_service = AIVoiceService()


@router.get(
    "/findings",
    response_model=FindingListResponse,
    summary="List all persisted findings across repositories with search and filters",
)
async def list_all_findings(
    category: Optional[str] = Query(None, description="Filter by category (SECURITY, QUALITY, etc.)"),
    severity: Optional[str] = Query(None, description="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW, INFO)"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (OPEN, RESOLVED, etc.)"),
    repository_id: Optional[str] = Query(None, description="Filter by repository ID"),
    search: Optional[str] = Query(None, description="Search by title, description, or file path"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> FindingListResponse:
    stmt = (
        select(Finding)
        .options(
            selectinload(Finding.evidence),
            selectinload(Finding.review_run)
            .selectinload(ReviewRun.review_job)
            .selectinload(ReviewJob.pull_request)
            .selectinload(PullRequest.repository),
        )
        .order_by(Finding.created_at.desc())
    )

    if category:
        stmt = stmt.where(Finding.category == category.upper())
    if severity:
        stmt = stmt.where(Finding.severity == severity.upper())
    if status_filter:
        stmt = stmt.where(Finding.status == status_filter.upper())
    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Finding.title.ilike(search_pattern),
                Finding.description.ilike(search_pattern),
                Finding.file_path.ilike(search_pattern),
            )
        )
    if repository_id:
        stmt = (
            stmt.join(Finding.review_run)
            .join(ReviewRun.review_job)
            .join(ReviewJob.pull_request)
            .where(PullRequest.repository_id == repository_id)
        )

    # Compute severity counts
    counts_stmt = select(Finding.severity, func.count(Finding.id)).group_by(Finding.severity)
    if category:
        counts_stmt = counts_stmt.where(Finding.category == category.upper())
    if status_filter:
        counts_stmt = counts_stmt.where(Finding.status == status_filter.upper())
    count_res = await db.execute(counts_stmt)
    severity_breakdown = {row[0].upper(): row[1] for row in count_res.all()}

    # Count total
    count_total_stmt = select(func.count(Finding.id))
    if category:
        count_total_stmt = count_total_stmt.where(Finding.category == category.upper())
    if severity:
        count_total_stmt = count_total_stmt.where(Finding.severity == severity.upper())
    if status_filter:
        count_total_stmt = count_total_stmt.where(Finding.status == status_filter.upper())
    if search:
        search_pattern = f"%{search}%"
        count_total_stmt = count_total_stmt.where(
            or_(
                Finding.title.ilike(search_pattern),
                Finding.description.ilike(search_pattern),
                Finding.file_path.ilike(search_pattern),
            )
        )
    total_count = (await db.execute(count_total_stmt)).scalar() or 0

    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    findings = result.scalars().all()

    items = []
    for f in findings:
        evidence_reads = [
            FindingEvidenceRead(
                id=ev.id,
                finding_id=ev.finding_id,
                source=ev.source,
                tool=ev.tool,
                rule_id=ev.rule_id,
                raw_message=ev.raw_message,
                code_snippet=ev.code_snippet,
                metadata_payload=ev.metadata_payload,
                created_at=ev.created_at,
            )
            for ev in f.evidence
        ]
        items.append(
            FindingRead(
                id=f.id,
                review_run_id=f.review_run_id,
                fingerprint=f.fingerprint,
                category=f.category,
                severity=f.severity,
                confidence=f.confidence,
                status=f.status,
                file_path=f.file_path,
                line_start=f.line_start,
                line_end=f.line_end,
                title=f.title,
                description=f.description,
                impact=f.impact,
                recommendation=f.recommendation,
                policy_reference=f.policy_reference,
                evidence_count=len(evidence_reads),
                evidence=evidence_reads,
                created_at=f.created_at,
            )
        )

    return FindingListResponse(
        items=items,
        total=total_count,
        severity_breakdown=severity_breakdown,
    )



@router.get(
    "/reviews/{review_id}/findings",
    response_model=FindingListResponse,
    summary="List findings for a review run",
    description="Retrieves normalized, deduplicated findings synthesized for a specific review run with optional filtering.",
)
async def list_review_findings(
    review_id: str,
    category: Optional[str] = Query(None, description="Filter by category (SECURITY, QUALITY, SECRET, etc.)"),
    severity: Optional[str] = Query(None, description="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW, INFO)"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (OPEN, RESOLVED, FALSE_POSITIVE, MITIGATED)"),
    db: AsyncSession = Depends(get_db),
):
    run_repo = ReviewRunRepository(db)
    review_run = await run_repo.get(review_id)
    if not review_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review run '{review_id}' not found.",
        )

    findings = await FindingService.list_findings_by_review(
        session=db,
        review_run_id=review_id,
        category=category,
        severity=severity,
        status=status_filter,
    )

    finding_repo = FindingRepository(db)
    severity_counts = await finding_repo.get_severity_counts(review_id)

    items = []
    for f in findings:
        evidence_reads = [
            FindingEvidenceRead(
                id=ev.id,
                finding_id=ev.finding_id,
                source=ev.source,
                tool=ev.tool,
                rule_id=ev.rule_id,
                raw_message=ev.raw_message,
                code_snippet=ev.code_snippet,
                metadata_payload=ev.metadata_payload,
                created_at=ev.created_at,
            )
            for ev in f.evidence
        ]
        items.append(
            FindingRead(
                id=f.id,
                review_run_id=f.review_run_id,
                fingerprint=f.fingerprint,
                category=f.category,
                severity=f.severity,
                confidence=f.confidence,
                status=f.status,
                file_path=f.file_path,
                line_start=f.line_start,
                line_end=f.line_end,
                title=f.title,
                description=f.description,
                impact=f.impact,
                recommendation=f.recommendation,
                policy_reference=f.policy_reference,
                evidence_count=len(evidence_reads),
                evidence=evidence_reads,
                created_at=f.created_at,
            )
        )

    return FindingListResponse(
        items=items,
        total=len(items),
        severity_breakdown=severity_counts,
    )


@router.get(
    "/findings/{finding_id}",
    response_model=FindingRead,
    summary="Get single finding details with evidence chain",
    description="Retrieves a comprehensive view of a finding including its full supporting evidence chain from scanners and agents.",
)
async def get_finding(
    finding_id: str,
    db: AsyncSession = Depends(get_db),
):
    finding = await FindingService.get_finding_by_id(db, finding_id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding with ID '{finding_id}' not found.",
        )

    evidence_reads = [
        FindingEvidenceRead(
            id=ev.id,
            finding_id=ev.finding_id,
            source=ev.source,
            tool=ev.tool,
            rule_id=ev.rule_id,
            raw_message=ev.raw_message,
            code_snippet=ev.code_snippet,
            metadata_payload=ev.metadata_payload,
            created_at=ev.created_at,
        )
        for ev in finding.evidence
    ]

    return FindingRead(
        id=finding.id,
        review_run_id=finding.review_run_id,
        fingerprint=finding.fingerprint,
        category=finding.category,
        severity=finding.severity,
        confidence=finding.confidence,
        status=finding.status,
        file_path=finding.file_path,
        line_start=finding.line_start,
        line_end=finding.line_end,
        title=finding.title,
        description=finding.description,
        impact=finding.impact,
        recommendation=finding.recommendation,
        policy_reference=finding.policy_reference,
        evidence_count=len(evidence_reads),
        evidence=evidence_reads,
        created_at=finding.created_at,
    )


@router.patch(
    "/findings/{finding_id}/status",
    response_model=FindingRead,
    summary="Update finding status (e.g. false positive, resolved)",
    description="Transitions a finding's lifecycle state with an immutable compliance audit record.",
)
async def update_finding_status(
    finding_id: str,
    payload: FindingStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    updated = await FindingService.update_finding_status(
        session=db,
        finding_id=finding_id,
        new_status=payload.status,
        actor="dashboard-user",
        reason=payload.reason,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding with ID '{finding_id}' not found.",
        )

    return await get_finding(finding_id, db)


@router.post(
    "/findings/{finding_id}/explain",
    response_model=FindingExplanationResponse,
    summary="Get multilingual AI explanation for finding",
    description="Provides detailed error explanation and fix instructions in English, Hindi, Hinglish, Urdu, Marathi, or Gujarati with speech script.",
)
async def explain_finding(
    finding_id: str,
    payload: FindingExplanationRequest,
    db: AsyncSession = Depends(get_db),
) -> FindingExplanationResponse:
    """Generates localized explanation and audio narration script for finding."""
    finding_repo = FindingRepository(db)
    finding = await finding_repo.get(finding_id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding with ID '{finding_id}' not found.",
        )

    return explanation_service.explain_finding(
        finding_id=finding.id,
        title=finding.title,
        description=finding.description,
        category=finding.category,
        severity=finding.severity,
        language=payload.language,
    )


@router.get(
    "/findings/{finding_id}/audio",
    summary="Stream AI Voice explanation audio for finding",
    description="Streams synthesized WAV audio narration explaining the finding in the requested language (en, hi, hinglish, ur, mr, gu).",
)
async def stream_finding_audio(
    finding_id: str,
    lang: str = Query("en", description="Target language: en, hi, hinglish, ur, mr, gu"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Streams synthesized PCM WAV voice audio for a finding."""
    finding_repo = FindingRepository(db)
    finding = await finding_repo.get(finding_id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding with ID '{finding_id}' not found.",
        )

    target_lang = SupportedLanguage.ENGLISH
    try:
        target_lang = SupportedLanguage(lang)
    except ValueError:
        pass

    explanation = explanation_service.explain_finding(
        finding_id=finding.id,
        title=finding.title,
        description=finding.description,
        category=finding.category,
        severity=finding.severity,
        language=target_lang,
    )

    wav_bytes = voice_service.synthesize_wav_stream(text=explanation.voice_script, lang=lang)
    return Response(content=wav_bytes, media_type="audio/wav")

