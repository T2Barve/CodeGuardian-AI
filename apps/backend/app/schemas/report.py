from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.risk import CategoryRiskBreakdown, RiskGrade, RiskLevel


class ReportFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"
    HTML = "html"


class ReportFindingItem(BaseModel):
    finding_id: str
    fingerprint: str
    category: str
    severity: str
    confidence: float
    file_path: str
    line_start: int
    line_end: int
    title: str
    description: str
    impact: Optional[str] = None
    recommendation: Optional[str] = None
    code_snippet: Optional[str] = None
    policy_reference: Optional[str] = None
    tools_involved: List[str] = Field(default_factory=list)


class ReportAgentSummary(BaseModel):
    agent_name: str
    status: str
    duration_ms: int
    token_usage: int = 0
    findings_count: int = 0
    error: Optional[str] = None


class ReviewReportSummary(BaseModel):
    review_run_id: str
    job_id: Optional[str] = None
    repo_name: str
    pr_number: int
    pr_title: str
    author: str
    commit_sha: str
    source_branch: str
    target_branch: str
    risk_score: float = Field(..., ge=0.0, le=100.0)
    risk_grade: RiskGrade
    risk_level: RiskLevel
    is_mergeable: bool
    recommended_action: str
    duration_ms: int
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int


class ReviewReport(BaseModel):
    summary: ReviewReportSummary
    category_breakdown: CategoryRiskBreakdown
    risk_driving_factors: List[str] = Field(default_factory=list)
    findings: List[ReportFindingItem] = Field(default_factory=list)
    agent_summaries: List[ReportAgentSummary] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    markdown_content: Optional[str] = None
