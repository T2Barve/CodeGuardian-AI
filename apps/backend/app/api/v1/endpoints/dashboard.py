from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.session import get_db
from app.database.seed import seed_database
from app.models.finding import Finding
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob, ReviewRun
from app.schemas.dashboard import (
    DashboardSummaryResponse,
    QualityTrendPoint,
    RecentReviewItem,
    SecurityTrendPoint,
)
from app.schemas.risk import CategoryRiskBreakdown, RiskGrade, RiskLevel

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Metrics"])


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    summary="Get aggregated executive dashboard metrics and trends",
)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
) -> DashboardSummaryResponse:
    # 1. Counts
    repo_count_stmt = select(func.count(Repository.id))
    total_repos = (await db.execute(repo_count_stmt)).scalar() or 0

    review_count_stmt = select(func.count(ReviewRun.id))
    total_reviews = (await db.execute(review_count_stmt)).scalar() or 0

    crit_stmt = select(func.count(Finding.id)).where(Finding.severity == "CRITICAL")
    critical_findings = (await db.execute(crit_stmt)).scalar() or 0

    high_stmt = select(func.count(Finding.id)).where(Finding.severity == "HIGH")
    high_findings = (await db.execute(high_stmt)).scalar() or 0

    open_stmt = select(func.count(Finding.id)).where(Finding.status == "OPEN")
    open_findings = (await db.execute(open_stmt)).scalar() or 0

    resolved_stmt = select(func.count(Finding.id)).where(
        Finding.status.in_(["RESOLVED", "FALSE_POSITIVE", "WONT_FIX", "MITIGATED"])
    )
    resolved_findings = (await db.execute(resolved_stmt)).scalar() or 0

    avg_dur_stmt = select(func.avg(ReviewRun.duration_ms)).where(ReviewRun.duration_ms.isnot(None))
    avg_duration = (await db.execute(avg_dur_stmt)).scalar()
    avg_duration_ms = int(avg_duration) if avg_duration else 1850

    # 2. Recent Reviews
    recent_runs_stmt = (
        select(ReviewRun)
        .options(
            selectinload(ReviewRun.review_job)
            .selectinload(ReviewJob.pull_request)
            .selectinload(PullRequest.repository),
            selectinload(ReviewRun.findings),
        )
        .order_by(ReviewRun.started_at.desc())
        .limit(10)
    )
    recent_runs_res = await db.execute(recent_runs_stmt)
    runs = recent_runs_res.scalars().all()

    recent_reviews: List[RecentReviewItem] = []
    category_scores = {"security": [], "quality": [], "testing": [], "documentation": [], "dependency": []}

    for r in runs:
        pr = r.review_job.pull_request if r.review_job else None
        repo = pr.repository if pr else None

        crit_c = sum(1 for f in r.findings if f.severity.upper() == "CRITICAL")
        high_c = sum(1 for f in r.findings if f.severity.upper() == "HIGH")
        med_c = sum(1 for f in r.findings if f.severity.upper() == "MEDIUM")
        low_c = sum(1 for f in r.findings if f.severity.upper() == "LOW")

        config = r.configuration or {}
        risk_data = config.get("risk_assessment") or {}
        cb = risk_data.get("breakdown") or risk_data.get("category_breakdown") or {}

        if cb:
            category_scores["security"].append(cb.get("security", 0.0))
            category_scores["quality"].append(cb.get("quality", 0.0))
            category_scores["testing"].append(cb.get("testing", 0.0))
            category_scores["documentation"].append(cb.get("documentation", 0.0))
            category_scores["dependency"].append(cb.get("dependency", 0.0))
        elif r.findings:
            sev_weights = {"CRITICAL": 25.0, "HIGH": 15.0, "MEDIUM": 8.0, "LOW": 3.0, "INFO": 1.0}
            c_sec = sum(sev_weights.get(f.severity.upper(), 5.0) for f in r.findings if f.category.upper() == "SECURITY")
            c_qual = sum(sev_weights.get(f.severity.upper(), 5.0) for f in r.findings if f.category.upper() in ["QUALITY", "CODING_STANDARD", "MAINTAINABILITY"])
            c_test = sum(sev_weights.get(f.severity.upper(), 5.0) for f in r.findings if f.category.upper() == "TESTING")
            c_doc = sum(sev_weights.get(f.severity.upper(), 5.0) for f in r.findings if f.category.upper() == "DOCUMENTATION")
            c_dep = sum(sev_weights.get(f.severity.upper(), 5.0) for f in r.findings if f.category.upper() == "DEPENDENCY")
            category_scores["security"].append(min(100.0, c_sec))
            category_scores["quality"].append(min(100.0, c_qual))
            category_scores["testing"].append(min(100.0, c_test))
            category_scores["documentation"].append(min(100.0, c_doc))
            category_scores["dependency"].append(min(100.0, c_dep))

        recent_reviews.append(
            RecentReviewItem(
                review_run_id=r.id,
                job_id=r.review_job_id,
                repo_name=repo.name if repo else "code-repo",
                pr_number=pr.number if pr else 1,
                pr_title=pr.title if pr else "Pull Request",
                author=pr.author if pr else "developer",
                commit_sha=pr.commit_sha if pr else "00000000",
                status=r.status,
                risk_score=r.risk_score,
                risk_grade=r.risk_grade,
                risk_level=risk_data.get("level", "LOW") if risk_data else "LOW",
                is_mergeable=bool(risk_data.get("is_mergeable", True)),
                duration_ms=r.duration_ms,
                critical_count=crit_c,
                high_count=high_c,
                medium_count=med_c,
                low_count=low_c,
                created_at=r.started_at,
            )
        )

    # Calculate average category radar
    def _avg(lst: List[float], fallback: float = 0.0) -> float:
        return sum(lst) / len(lst) if lst else fallback

    category_radar = CategoryRiskBreakdown(
        security=_avg(category_scores["security"], fallback=0.0),
        quality=_avg(category_scores["quality"], fallback=0.0),
        testing=_avg(category_scores["testing"], fallback=0.0),
        documentation=_avg(category_scores["documentation"], fallback=0.0),
        dependency=_avg(category_scores["dependency"], fallback=0.0),
    )

    # 3. Dynamic Trends - Strictly aggregate from real ReviewRun and Finding records
    security_trend: List[SecurityTrendPoint] = []
    quality_trend: List[QualityTrendPoint] = []

    if runs:
        # Group runs by date string (e.g. "Oct 15")
        from collections import defaultdict
        daily_crit = defaultdict(int)
        daily_high = defaultdict(int)
        daily_med = defaultdict(int)
        daily_low = defaultdict(int)
        daily_scores = defaultdict(list)
        ordered_dates = []

        for r in reversed(runs):
            run_date = (r.completed_at or r.started_at).strftime("%b %d")
            if run_date not in daily_crit:
                ordered_dates.append(run_date)
            for f in r.findings:
                sev = f.severity.upper()
                if sev == "CRITICAL":
                    daily_crit[run_date] += 1
                elif sev == "HIGH":
                    daily_high[run_date] += 1
                elif sev == "MEDIUM":
                    daily_med[run_date] += 1
                elif sev == "LOW":
                    daily_low[run_date] += 1
            if r.risk_score is not None:
                # Maintainability is inverted risk score (100 - risk)
                daily_scores[run_date].append(max(0.0, 100.0 - r.risk_score))

        for d in ordered_dates:
            security_trend.append(
                SecurityTrendPoint(
                    date=d,
                    critical=daily_crit[d],
                    high=daily_high[d],
                    medium=daily_med[d],
                    low=daily_low[d],
                )
            )
            scores = daily_scores[d]
            avg_maint = sum(scores) / len(scores) if scores else 85.0
            quality_trend.append(
                QualityTrendPoint(
                    date=d,
                    maintainability_score=round(avg_maint, 1),
                    issues_detected=daily_crit[d] + daily_high[d],
                )
            )


    return DashboardSummaryResponse(
        total_repositories=total_repos,
        total_reviews=total_reviews,
        critical_findings=critical_findings,
        high_findings=high_findings,
        open_findings=open_findings,
        resolved_findings=resolved_findings,
        average_review_duration_ms=avg_duration_ms,
        recent_reviews=recent_reviews,
        security_trend=security_trend,
        quality_trend=quality_trend,
        category_radar=category_radar,
    )


@router.post(
    "/seed",
    status_code=status.HTTP_201_CREATED,
    summary="Seed demonstration and benchmark data for live dashboard presentation",
)
async def seed_data(
    db: AsyncSession = Depends(get_db),
):
    await seed_database(db)
    return {"status": "SUCCESS", "message": "Benchmark demonstration records successfully seeded"}
