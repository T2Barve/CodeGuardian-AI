from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ReviewJobPayload(BaseModel):
    """Payload representing a review job queued for asynchronous worker processing."""

    job_id: str = Field(..., description="Unique UUID of the ReviewJob record in the database")
    pull_request_id: str = Field(..., description="UUID of the PullRequest entity")
    repo_name: str = Field(..., description="Repository name")
    repo_owner: str = Field(..., description="Repository owner / organization")
    pr_number: int = Field(..., description="Pull request number")
    commit_sha: str = Field(..., description="Commit SHA to be scanned and reviewed")
    action: str = Field(default="opened", description="PR action that triggered the review")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp when the job was enqueued",
    )
    retry_count: int = Field(default=0, description="Number of times this job has been retried")
    last_error: Optional[str] = Field(default=None, description="Diagnostic error from previous failure")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional contextual metadata for worker execution"
    )


class QueueMetrics(BaseModel):
    """Observability metrics for Redis review queue lengths."""

    pending_jobs: int = Field(..., description="Number of jobs waiting to be dequeued in queue:reviews")
    processing_jobs: int = Field(
        ..., description="Number of in-flight jobs currently being processed in queue:reviews:processing"
    )
    dlq_jobs: int = Field(..., description="Number of failed jobs routed to dead-letter queue dlq:reviews")
