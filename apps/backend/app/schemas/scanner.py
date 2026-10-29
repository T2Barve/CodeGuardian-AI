from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ScannerSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class ScannerCategory(str, Enum):
    SECURITY = "SECURITY"
    QUALITY = "QUALITY"
    SECRET = "SECRET"
    VULNERABILITY = "VULNERABILITY"
    COMPLEXITY = "COMPLEXITY"
    SYNTAX = "SYNTAX"


class NormalizedScanResult(BaseModel):
    """
    Standardized finding format output by all static analysis scanner adapters.
    Decouples raw tool output formats from downstream agents, aggregators, and risk engines.
    """

    scanner: str = Field(..., description="Tool name: semgrep, bandit, gitleaks, eslint")
    rule_id: str = Field(..., description="Unique tool rule identifier (e.g. B608, CWE-89, generic-api-key)")
    category: ScannerCategory = Field(default=ScannerCategory.SECURITY, description="Finding category")
    severity: ScannerSeverity = Field(..., description="Normalized severity level")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Detection confidence score (0.0 to 1.0)")
    file_path: str = Field(..., description="Relative repository file path where violation occurred")
    line_start: Optional[int] = Field(default=None, description="Starting line number (1-indexed)")
    line_end: Optional[int] = Field(default=None, description="Ending line number (1-indexed)")
    title: str = Field(..., description="Concise human-readable finding title")
    message: str = Field(..., description="Explanation of the vulnerability or flaw")
    code_snippet: Optional[str] = Field(default=None, description="Pertinent code extract showing the issue")
    raw_output: Optional[Dict[str, Any]] = Field(
        default=None, description="Preserved verbatim scanner output for debugging/audit"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Diagnostic metadata (e.g. CWE, OWASP, rule tags)"
    )


class ScannerExecutionSummary(BaseModel):
    """Execution telemetry for a single scanner tool run."""

    scanner: str
    status: str  # SUCCESS, TIMEOUT, FAILED, SKIPPED
    duration_ms: int
    findings_count: int
    error_message: Optional[str] = None
