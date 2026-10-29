from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class PullRequestRead(BaseModel):
    id: str
    github_pr_id: int
    repository_id: str
    repo_name: str
    repo_owner: str
    repo_full_name: str
    number: int
    title: str
    author: str
    source_branch: str
    target_branch: str
    commit_sha: str
    status: str
    latest_review_run_id: Optional[str] = None
    latest_risk_score: Optional[float] = None
    latest_risk_grade: Optional[str] = None
    latest_risk_level: Optional[str] = None
    is_mergeable: bool = True
    critical_count: int = 0
    high_count: int = 0
    total_findings: int = 0
    last_analyzed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PullRequestListResponse(BaseModel):
    total: int
    items: List[PullRequestRead] = Field(default_factory=list)


class PullRequestAnalyzeRequest(BaseModel):
    action: Optional[str] = Field(default="manual", description="Trigger reason (manual, re-analyze)")


class PullRequestAnalyzeResponse(BaseModel):
    job_id: str
    pull_request_id: str
    status: str
    message: str
