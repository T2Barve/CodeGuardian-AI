from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.risk import CategoryRiskBreakdown, RiskGrade, RiskLevel


class RecentReviewItem(BaseModel):
    review_run_id: str
    job_id: str
    repo_name: str
    pr_number: int
    pr_title: str
    author: str
    commit_sha: str
    status: str
    risk_score: Optional[float] = None
    risk_grade: Optional[str] = None
    risk_level: Optional[str] = None
    is_mergeable: bool = True
    duration_ms: Optional[int] = None
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    created_at: datetime


class SecurityTrendPoint(BaseModel):
    date: str
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class QualityTrendPoint(BaseModel):
    date: str
    maintainability_score: float = 0.0
    issues_detected: int = 0


class DashboardSummaryResponse(BaseModel):
    total_repositories: int
    total_reviews: int
    critical_findings: int
    high_findings: int
    open_findings: int
    resolved_findings: int
    average_review_duration_ms: int
    recent_reviews: List[RecentReviewItem] = Field(default_factory=list)
    security_trend: List[SecurityTrendPoint] = Field(default_factory=list)
    quality_trend: List[QualityTrendPoint] = Field(default_factory=list)
    category_radar: CategoryRiskBreakdown
