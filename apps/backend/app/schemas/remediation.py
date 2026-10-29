from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RemediationStatus(str, Enum):
    REQUESTED = "REQUESTED"
    GENERATING = "GENERATING"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    APPLIED = "APPLIED"


class ValidationStageStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ValidationStageResult(BaseModel):
    """Result of an individual validation stage within the sandbox pipeline."""

    stage: str = Field(..., description="Stage name (e.g., syntax_check, patch_application)")
    status: ValidationStageStatus = Field(..., description="Stage outcome: PASSED, FAILED, or SKIPPED")
    message: str = Field(..., description="Concise human-readable explanation of outcome")
    details: Optional[str] = Field(default=None, description="Detailed diagnostic or error output")
    duration_ms: int = Field(default=0, description="Execution time of the stage in milliseconds")


class RemediationValidationResult(BaseModel):
    """Aggregated result of the 5-stage sandboxed validation pipeline."""

    patch_application: ValidationStageResult
    syntax_check: ValidationStageResult
    scanner_check: ValidationStageResult
    unit_tests: ValidationStageResult
    regression_check: ValidationStageResult
    overall: ValidationStageStatus = Field(..., description="PASSED if all required stages pass, else FAILED")
    can_create_pr: bool = Field(default=False, description="True if patch is safely mergeable into Fix PR")
    error_summary: Optional[str] = Field(default=None, description="High-level error summary if validation failed")


class RemediationCandidate(BaseModel):
    """AI-synthesized candidate remediation patch before validation."""

    patch: str = Field(..., description="Unified diff formatted git patch")
    target_file: str = Field(..., description="Relative path of file to be modified")
    explanation: str = Field(..., description="Rationale for the proposed code change")
    policy_reference: Optional[str] = Field(default=None, description="Policy citation guiding the fix")


class RemediationRequest(BaseModel):
    """Request payload to initiate AI remediation."""

    custom_instructions: Optional[str] = Field(
        default=None,
        description="Optional developer guidelines or constraints for the patch generator",
    )


class RemediationResponse(BaseModel):
    """Response model for a remediation attempt."""

    id: str = Field(..., description="RemediationAttempt UUID")
    finding_id: str = Field(..., description="ID of the finding being remediated")
    status: RemediationStatus = Field(..., description="Current status of the remediation attempt")
    patch: str = Field(..., description="Unified diff patch content")
    target_file: Optional[str] = Field(default=None, description="File path targeted by the patch")
    explanation: Optional[str] = Field(default=None, description="Explanation of the fix")
    validation_result: Optional[Dict[str, Any]] = Field(default=None, description="Detailed 5-stage validation results")
    error_message: Optional[str] = Field(default=None, description="Diagnostic error message if rejected or failed")
    can_create_pr: bool = Field(default=False, description="Whether this patch is validated and ready for Fix PR")
    created_at: datetime = Field(..., description="Timestamp when attempt was requested")
    updated_at: Optional[datetime] = Field(default=None, description="Timestamp of latest update")


class RemediationListResponse(BaseModel):
    """List container of remediation attempts for a finding."""

    finding_id: str
    total: int
    items: List[RemediationResponse]


class FixPRCreateRequest(BaseModel):
    """Request payload to create a GitHub Fix Pull Request for a validated remediation."""

    remediation_attempt_id: Optional[str] = Field(default=None, description="UUID of the validated RemediationAttempt")
    branch_name: Optional[str] = Field(default=None, description="Optional custom branch name")
    custom_title: Optional[str] = Field(default=None, description="Optional custom PR title")
    custom_body: Optional[str] = Field(default=None, description="Optional custom PR description")



class FixPRResponse(BaseModel):
    """Details of a submitted GitHub Fix Pull Request."""

    id: str = Field(..., description="FixPR entity UUID")
    remediation_attempt_id: str = Field(..., description="Associated RemediationAttempt UUID")
    finding_id: str = Field(..., description="Associated Finding UUID")
    repo_name: str = Field(..., description="Repository full name")
    github_pr_id: Optional[int] = Field(default=None, description="GitHub internal PR ID")
    number: Optional[int] = Field(default=None, description="Pull Request sequence number")
    url: str = Field(..., description="Direct HTML URL to the created Fix PR")
    branch_name: str = Field(..., description="Branch name created for the fix")
    base_branch: str = Field(..., description="Target base branch")
    status: str = Field(default="OPEN", description="Fix PR status: OPEN, MERGED, CLOSED")
    created_at: datetime = Field(..., description="Timestamp of Fix PR creation")

