"""
CodeGuardian AI — Finding Aggregation and Deduplication Engine
Provides deterministic fingerprinting, multi-tool correlation, evidence merging, and persistence.
"""

from app.findings.correlation import (
    CorrelatedFinding,
    FindingEvidenceItem,
    combine_confidence,
    correlate_findings,
    resolve_highest_severity,
)
from app.findings.engine import FindingEngine
from app.findings.fingerprint import (
    generate_finding_fingerprint,
    get_canonical_issue_type,
    normalize_file_path,
)
from app.findings.service import FindingService

__all__ = [
    "generate_finding_fingerprint",
    "get_canonical_issue_type",
    "normalize_file_path",
    "CorrelatedFinding",
    "FindingEvidenceItem",
    "correlate_findings",
    "combine_confidence",
    "resolve_highest_severity",
    "FindingEngine",
    "FindingService",
]
