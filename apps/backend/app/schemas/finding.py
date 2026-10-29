from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FindingEvidenceRead(BaseModel):
    """Verbatim tool or agent evidence supporting a finding."""

    id: str = Field(..., description="Unique evidence ID")
    finding_id: str = Field(..., description="Foreign key to parent Finding")
    source: str = Field(..., description="Evidence source type: SCANNER or AGENT")
    tool: str = Field(..., description="Tool name: bandit, semgrep, gitleaks, eslint, etc.")
    rule_id: Optional[str] = Field(None, description="Specific rule or checker identifier")
    raw_message: str = Field(..., description="Verbatim message from the tool")
    code_snippet: Optional[str] = Field(None, description="Source code snippet showing the violation")
    metadata_payload: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic metadata (CWE, OWASP, etc.)")
    created_at: datetime = Field(..., description="Timestamp when evidence was ingested")

    model_config = {"from_attributes": True}


class FindingRead(BaseModel):
    """Normalized, deduplicated finding for dashboard and API consumers."""

    id: str = Field(..., description="Unique finding ID")
    review_run_id: str = Field(..., description="Review run during which finding was identified")
    fingerprint: str = Field(..., description="Deterministic SHA-256 fingerprint for cross-run tracking")
    category: str = Field(..., description="Finding category: SECURITY, QUALITY, SECRET, etc.")
    severity: str = Field(..., description="Severity level: CRITICAL, HIGH, MEDIUM, LOW, INFO")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0")
    status: str = Field(default="OPEN", description="Finding lifecycle status: OPEN, RESOLVED, FALSE_POSITIVE, MITIGATED")
    file_path: str = Field(..., description="Relative repository file path")
    line_start: Optional[int] = Field(None, description="Starting line number (1-indexed)")
    line_end: Optional[int] = Field(None, description="Ending line number (1-indexed)")
    title: str = Field(..., description="Concise human-readable finding title")
    description: str = Field(..., description="Detailed description of the vulnerability or flaw")
    impact: Optional[str] = Field(None, description="Potential security or operational impact")
    recommendation: Optional[str] = Field(None, description="Actionable remediation recommendation")
    policy_reference: Optional[str] = Field(None, description="Citation of violated organizational policy or standard")
    evidence_count: int = Field(default=0, description="Total number of tool/agent evidence items supporting finding")
    evidence: Optional[List[FindingEvidenceRead]] = Field(default=None, description="Full evidence chain if loaded")
    created_at: datetime = Field(..., description="Timestamp when finding was synthesized")

    model_config = {"from_attributes": True}


class FindingStatusUpdateRequest(BaseModel):
    """Request payload for updating the review status of a finding."""

    status: str = Field(
        ...,
        pattern="^(OPEN|RESOLVED|FALSE_POSITIVE|MITIGATED)$",
        description="Updated finding status: OPEN, RESOLVED, FALSE_POSITIVE, MITIGATED",
    )
    reason: Optional[str] = Field(
        None,
        max_length=1000,
        description="Reason or rationale for status transition (e.g. audit note for false positive)",
    )


class FindingListResponse(BaseModel):
    """Paginated or filtered list of findings with severity summary."""

    items: List[FindingRead] = Field(default_factory=list)
    total: int = Field(default=0)
    severity_breakdown: Dict[str, int] = Field(default_factory=dict)
