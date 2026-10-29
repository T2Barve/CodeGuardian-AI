from typing import Dict, List, Optional

from app.findings.correlation import CorrelatedFinding, correlate_findings
from app.schemas.scanner import NormalizedScanResult
from app.utils.logging import get_logger

logger = get_logger("codeguardian.findings.engine")


class FindingEngine:
    """
    Finding Aggregation and Deduplication Engine.
    Converts heterogeneous tool outputs into correlated, fingerprint-traceable findings
    while retaining the complete chain of underlying evidence.
    """

    def __init__(self, line_tolerance: int = 2):
        self.line_tolerance = line_tolerance

    def process_scan_results(
        self,
        raw_results: List[NormalizedScanResult],
    ) -> List[CorrelatedFinding]:
        """
        Executes normalization, clustering, and deduplication across scan results.

        Returns:
            List of CorrelatedFinding instances with preserved evidence.
        """
        if not raw_results:
            logger.info("No scanner results provided to finding engine; returning empty list.")
            return []

        logger.info(
            f"FindingEngine processing {len(raw_results)} raw scanner results",
            extra={"raw_count": len(raw_results)},
        )

        correlated = correlate_findings(
            raw_results=raw_results,
            line_tolerance=self.line_tolerance,
        )

        dedup_count = len(raw_results) - len(correlated)
        logger.info(
            f"FindingEngine synthesized {len(correlated)} correlated findings (deduplicated {dedup_count} duplicates)",
            extra={
                "raw_count": len(raw_results),
                "correlated_count": len(correlated),
                "deduplicated_count": dedup_count,
            },
        )

        return correlated

    @staticmethod
    def get_severity_breakdown(findings: List[CorrelatedFinding]) -> Dict[str, int]:
        """Calculates finding counts grouped by severity."""
        counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
        for f in findings:
            sev = f.severity.upper()
            counts[sev] = counts.get(sev, 0) + 1
        return counts
