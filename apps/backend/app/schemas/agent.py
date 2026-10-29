from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentRunResponse(BaseModel):
    """Schema representing an individual specialist or supervisor agent run."""
    id: str
    review_run_id: str
    agent_name: str
    status: str
    input_reference: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    error: Optional[str] = None
    created_at: datetime


class AgentRunsListResponse(BaseModel):
    """Schema for listing all agent runs associated with a review."""
    review_run_id: str
    total_agents: int
    agents: List[AgentRunResponse]


class FileClassificationRequest(BaseModel):
    """Request payload for file classification and routing analysis."""
    changed_files: List[str]
    repo_name: Optional[str] = "example-repo"
    pr_number: Optional[int] = 1


class FileClassificationResponse(BaseModel):
    """Response containing activated agents, partitions, and architectural rationale."""
    active_agents: List[str]
    file_partitioning: Dict[str, List[str]]
    rationale: str


# ==============================================================================
# SPECIALIST AGENT SCHEMAS (PHASE 9)
# ==============================================================================

class SecurityFindingItem(BaseModel):
    """Structured security vulnerability finding evaluated by the Security Agent."""
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None
    severity: str = "MEDIUM"  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    confidence: float = 0.85
    file_path: str
    line_start: int = 1
    line_end: int = 1
    title: str
    description: str
    exploitability_analysis: str
    recommendation: str
    evidence_source: str
    rule_id: Optional[str] = None
    policy_reference: Optional[str] = None


class SecurityAgentOutput(BaseModel):
    """Aggregate output from the Security Specialist Agent."""
    findings: List[SecurityFindingItem] = Field(default_factory=list)
    summary: str = ""
    threat_level: str = "LOW"  # CRITICAL, HIGH, MEDIUM, LOW


class QualityFindingItem(BaseModel):
    """Structured code quality or maintainability issue identified by Quality Agent."""
    severity: str = "LOW"  # HIGH, MEDIUM, LOW, INFO
    confidence: float = 0.85
    file_path: str
    line_start: int = 1
    line_end: int = 1
    title: str
    code_smell_type: str = "MAINTAINABILITY"  # COMPLEXITY, DUPLICATION, NAMING, COUPLING, ERROR_HANDLING
    description: str
    recommendation: str
    policy_reference: Optional[str] = None


class QualityAgentOutput(BaseModel):
    """Aggregate output from the Quality Specialist Agent."""
    findings: List[QualityFindingItem] = Field(default_factory=list)
    summary: str = ""
    maintainability_rating: str = "A"  # A, B, C, D, F


class TestingGapItem(BaseModel):
    """Structured test gap analysis item produced by the Testing Agent."""
    file_path: str
    untested_symbol: str
    risk_level: str = "MEDIUM"  # HIGH, MEDIUM, LOW
    missing_test_type: str = "UNIT"  # UNIT, INTEGRATION, REGRESSION, EDGE_CASE
    rationale: str
    suggested_test_skeleton: Optional[str] = None


class TestingAgentOutput(BaseModel):
    """Aggregate output from the Testing Specialist Agent."""
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    test_gaps: List[TestingGapItem] = Field(default_factory=list)
    summary: str = ""
    coverage_risk: str = "LOW"  # HIGH, MEDIUM, LOW


class DocumentationFindingItem(BaseModel):
    """Structured documentation gap finding evaluated by Documentation Agent."""
    file_path: str
    line_start: int = 1
    line_end: int = 1
    title: str
    doc_type: str = "DOCSTRING"  # DOCSTRING, README, API_DOC, TYPE_ANNOTATION
    description: str
    recommendation: str


class DocumentationAgentOutput(BaseModel):
    """Aggregate output from the Documentation Specialist Agent."""
    findings: List[DocumentationFindingItem] = Field(default_factory=list)
    summary: str = ""
    documentation_health: str = "GOOD"  # GOOD, FAIR, POOR


class DependencyFindingItem(BaseModel):
    """Structured package or dependency issue identified by Dependency Agent."""
    package_name: str
    version_specifier: str
    manifest_file: str
    severity: str = "LOW"  # HIGH, MEDIUM, LOW, INFO
    risk_type: str = "UNPINNED_VERSION"  # UNPINNED_VERSION, SUSPICIOUS_PACKAGE, WILDCARD_VERSION, OUTDATED
    description: str
    recommendation: str


class DependencyAgentOutput(BaseModel):
    """Aggregate output from the Dependency Specialist Agent."""
    findings: List[DependencyFindingItem] = Field(default_factory=list)
    summary: str = ""
    dependencies_analyzed: int = 0

