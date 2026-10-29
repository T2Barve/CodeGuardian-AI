from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class PullRequestSummary(BaseModel):
    id: str
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
    created_at: datetime
    updated_at: datetime


class RepositoryRead(BaseModel):
    id: str
    github_repo_id: int
    name: str
    owner: str
    url: str
    default_branch: str
    language: Optional[str] = None
    is_active: bool
    pull_requests_count: int = 0
    reviews_count: int = 0
    last_reviewed_at: Optional[datetime] = None
    health_status: str = "HEALTHY"
    created_at: datetime
    updated_at: datetime


class RepositoryDetail(RepositoryRead):
    recent_pull_requests: List[PullRequestSummary] = Field(default_factory=list)


class RepositoryValidateRequest(BaseModel):
    url: str = Field(..., description="GitHub repository URL (e.g. https://github.com/owner/repository)")


class RepositoryValidateResponse(BaseModel):
    owner: str
    name: str
    full_name: str
    url: str
    default_branch: str
    language: Optional[str] = None
    description: Optional[str] = None
    is_private: bool = False
    open_issues_count: int = 0
    open_pull_requests_count: int = 0
    stargazers_count: int = 0
    forks_count: int = 0
    exists_in_database: bool = False
    monitoring_status: str = "READY_TO_CONNECT"
    webhook_url: str = "/api/v1/github/webhook"


class RepositoryCreateRequest(BaseModel):
    url: str = Field(..., description="GitHub repository URL")
    owner: Optional[str] = None
    name: Optional[str] = None
    github_repo_id: Optional[int] = None
    default_branch: Optional[str] = "main"
    language: Optional[str] = None
    is_active: bool = True
    enable_pr_monitoring: bool = True
    auto_sync_prs: bool = True


class RepositoryMonitoringUpdateRequest(BaseModel):
    is_active: bool = Field(..., description="Enable or disable automated PR monitoring")


class RepositorySyncResponse(BaseModel):
    repository_id: str
    synced_pull_requests_count: int
    pull_requests: List[PullRequestSummary] = Field(default_factory=list)
    message: str


class GitHubAccessibleRepo(BaseModel):
    id: int
    name: str
    full_name: str
    owner: str
    url: str
    default_branch: str
    is_private: bool
    language: Optional[str] = None
    description: Optional[str] = None


class GitHubAccessibleReposResponse(BaseModel):
    configured: bool
    total: int
    repositories: List[GitHubAccessibleRepo] = Field(default_factory=list)
    message: Optional[str] = None
