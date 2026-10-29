from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GitHubUser(BaseModel):
    """GitHub user identity model."""

    id: int = Field(..., description="Unique GitHub numeric user ID")
    login: str = Field(..., description="GitHub username handle")
    type: Optional[str] = Field(default="User", description="Account type (User or Bot)")


class GitHubRepo(BaseModel):
    """GitHub repository reference model."""

    id: int = Field(..., description="GitHub unique repository ID")
    name: str = Field(..., description="Repository name")
    full_name: str = Field(..., description="Full repository name (owner/name)")
    owner: GitHubUser = Field(..., description="Repository owner details")
    html_url: str = Field(..., description="Web URL to repository")
    default_branch: str = Field(default="main", description="Repository default branch name")
    language: Optional[str] = Field(default=None, description="Primary language of the repository")
    private: bool = Field(default=False, description="Whether the repository is private")


class GitHubBranch(BaseModel):
    """GitHub branch reference with commit SHA."""

    ref: str = Field(..., description="Branch name / ref")
    sha: str = Field(..., description="Git commit SHA-1")
    repo: Optional[GitHubRepo] = Field(default=None, description="Repository reference")
    user: Optional[GitHubUser] = Field(default=None, description="User reference")


class GitHubPullRequest(BaseModel):
    """GitHub Pull Request payload object."""

    id: int = Field(..., description="GitHub internal PR ID")
    number: int = Field(..., description="PR sequence number in repository")
    title: str = Field(..., description="Pull request title")
    state: str = Field(default="open", description="PR state: open or closed")
    body: Optional[str] = Field(default=None, description="PR markdown description")
    head: GitHubBranch = Field(..., description="Source branch / commit SHA")
    base: GitHubBranch = Field(..., description="Target branch / commit SHA")
    user: GitHubUser = Field(..., description="Pull request author")
    html_url: Optional[str] = Field(default=None, description="Direct web link to PR")
    merged: Optional[bool] = Field(default=False, description="Whether PR is merged")


class GitHubInstallation(BaseModel):
    """GitHub App installation identifier."""

    id: int = Field(..., description="Installation ID")


class PullRequestWebhookPayload(BaseModel):
    """Complete GitHub Pull Request Webhook payload."""

    action: str = Field(
        ...,
        description="PR action: opened, synchronize, reopened, closed, edited, etc.",
    )
    number: int = Field(..., description="Pull request number")
    pull_request: GitHubPullRequest = Field(..., description="Pull request details")
    repository: GitHubRepo = Field(..., description="Repository where PR was opened")
    sender: Optional[GitHubUser] = Field(default=None, description="Actor triggering webhook")
    installation: Optional[GitHubInstallation] = Field(
        default=None, description="GitHub App installation details"
    )


class WebhookResponse(BaseModel):
    """Acknowledgement response for ingested GitHub webhooks."""

    status: str = Field(
        ...,
        description="Outcome status: 'enqueued' (accepted for review) or 'ignored' (non-actionable).",
    )
    job_id: Optional[str] = Field(
        default=None,
        description="Assigned ReviewJob UUID if review workflow was enqueued.",
    )
    delivery_id: str = Field(
        ...,
        description="GitHub delivery UUID from X-GitHub-Delivery header.",
    )
    event: str = Field(
        ...,
        description="GitHub event type (e.g. pull_request).",
    )
    action: str = Field(
        ...,
        description="Event action (e.g. opened, synchronize).",
    )
    message: Optional[str] = Field(
        default=None,
        description="Optional diagnostic or explanatory information.",
    )


class GitHubCheckRunOutput(BaseModel):
    """Output payload for GitHub check runs."""

    title: str = Field(..., description="Check run summary title")
    summary: str = Field(..., description="Markdown summary of check run results")
    text: Optional[str] = Field(default=None, description="Extended markdown details")


class GitHubCheckRunCreate(BaseModel):
    """Request payload to create a GitHub Check Run."""

    name: str = Field(default="CodeGuardian AI", description="Check run name")
    head_sha: str = Field(..., description="Commit SHA being checked")
    status: str = Field(default="in_progress", description="Check status: queued, in_progress, completed")
    conclusion: Optional[str] = Field(
        default=None,
        description="Conclusion: success, failure, neutral, action_required",
    )
    output: Optional[GitHubCheckRunOutput] = Field(
        default=None, description="Check run visual output"
    )


class GitHubCommentCreate(BaseModel):
    """Request payload to create a PR comment."""

    body: str = Field(..., description="Markdown body of the review comment")
    commit_id: Optional[str] = Field(default=None, description="Commit SHA for inline comment")
    path: Optional[str] = Field(default=None, description="File path for inline comment")
    line: Optional[int] = Field(default=None, description="Line number for inline comment")


class GitHubPublishResult(BaseModel):
    """Result of publishing review findings to GitHub Check Runs and PR comments."""

    review_run_id: str = Field(..., description="ReviewRun UUID")
    repo_name: str = Field(..., description="Repository full name")
    pr_number: int = Field(..., description="Pull Request number")
    commit_sha: str = Field(..., description="Commit SHA published to")
    check_run_id: Optional[int] = Field(default=None, description="GitHub Check Run ID")
    check_run_status: str = Field(default="completed", description="Check run status")
    check_run_conclusion: str = Field(..., description="success, failure, neutral")
    comment_id: Optional[int] = Field(default=None, description="GitHub Issue Comment ID")
    comment_action: str = Field(default="CREATED", description="CREATED, UPDATED, or SKIPPED")
    annotations_count: int = Field(default=0, description="Number of annotations submitted")
    inline_comments_count: int = Field(default=0, description="Number of inline comments posted")
    status: str = Field(default="PUBLISHED", description="Overall publish status")
    details: Optional[str] = Field(default=None, description="Diagnostic notes or error explanations")


class GitHubReportPreview(BaseModel):
    """Preview of GitHub PR comment and Check Run annotations before publishing."""

    review_run_id: str = Field(..., description="ReviewRun UUID")
    pr_number: int = Field(..., description="Pull Request number")
    comment_markdown: str = Field(..., description="Formatted markdown comment with anti-spam marker")
    comment_marker: str = Field(..., description="Marker string used for deduplication")
    check_run_title: str = Field(..., description="Title of the Check Run")
    check_run_conclusion: str = Field(..., description="Projected conclusion: success, failure, neutral")
    annotations_count: int = Field(..., description="Count of line-level annotations")
    annotations: List[Dict[str, Any]] = Field(default_factory=list, description="Sample annotations list")

