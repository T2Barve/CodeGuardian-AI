import asyncio
import time
from typing import Dict, List, Optional, Set, Tuple

from app.scanners.bandit import BanditScanner
from app.scanners.base import BaseScanner, ScannerExecutionError, ScannerTimeoutError
from app.scanners.eslint import ESLintScanner
from app.scanners.gitleaks import GitleaksScanner
from app.scanners.semgrep import SemgrepScanner
from app.schemas.scanner import (
    NormalizedScanResult,
    ScannerCategory,
    ScannerExecutionSummary,
    ScannerSeverity,
)
from app.utils.logging import get_logger

logger = get_logger("codeguardian.scanners.engine")


class ScannerEngine:
    """
    Unified orchestrator and registry for static analysis scanners.
    Executes SAST adapters (Bandit, Semgrep, Gitleaks, ESLint) concurrently,
    manages execution timeouts, isolates failures, and aggregates standardized findings.
    """

    def __init__(self, scanners: Optional[List[BaseScanner]] = None):
        if scanners is None:
            self._scanners: Dict[str, BaseScanner] = {
                "bandit": BanditScanner(),
                "semgrep": SemgrepScanner(),
                "gitleaks": GitleaksScanner(),
                "eslint": ESLintScanner(),
            }
        else:
            self._scanners = {s.name: s for s in scanners}

    def register_scanner(self, scanner: BaseScanner) -> None:
        """Registers or overrides a scanner adapter."""
        self._scanners[scanner.name] = scanner
        logger.info(f"Registered scanner adapter '{scanner.name}'")

    def unregister_scanner(self, name: str) -> Optional[BaseScanner]:
        """Unregisters a scanner adapter by name."""
        return self._scanners.pop(name, None)

    def get_scanner(self, name: str) -> Optional[BaseScanner]:
        """Retrieves a scanner adapter by name."""
        return self._scanners.get(name)

    def list_scanners(self) -> List[str]:
        """Returns the names of all registered scanners."""
        return list(self._scanners.keys())

    def get_available_scanners(self) -> List[str]:
        """Returns names of registered scanners whose underlying analyzers are available."""
        return [name for name, scanner in self._scanners.items() if scanner.is_available()]

    async def _execute_single_scanner(
        self,
        scanner: BaseScanner,
        repo_path: str,
        changed_files: Optional[List[str]],
    ) -> Tuple[str, List[NormalizedScanResult], ScannerExecutionSummary]:
        """
        Executes a single scanner safely, capturing execution telemetry and errors.
        """
        start_time = time.perf_counter()
        scanner_name = scanner.name
        try:
            findings = await scanner.scan(repo_path, changed_files=changed_files)
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            summary = ScannerExecutionSummary(
                scanner=scanner_name,
                status="SUCCESS",
                duration_ms=duration_ms,
                findings_count=len(findings),
                error_message=None,
            )
            logger.info(
                f"Scanner '{scanner_name}' completed",
                extra={"scanner": scanner_name, "findings": len(findings), "duration_ms": duration_ms},
            )
            return scanner_name, findings, summary

        except ScannerTimeoutError as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warning(
                f"Scanner '{scanner_name}' timed out",
                extra={"scanner": scanner_name, "duration_ms": duration_ms, "error": str(exc)},
            )
            summary = ScannerExecutionSummary(
                scanner=scanner_name,
                status="TIMEOUT",
                duration_ms=duration_ms,
                findings_count=0,
                error_message=str(exc),
            )
            return scanner_name, [], summary

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(
                f"Scanner '{scanner_name}' encountered unexpected failure",
                extra={"scanner": scanner_name, "duration_ms": duration_ms, "error": str(exc)},
            )
            summary = ScannerExecutionSummary(
                scanner=scanner_name,
                status="FAILED",
                duration_ms=duration_ms,
                findings_count=0,
                error_message=str(exc),
            )
            return scanner_name, [], summary

    async def scan_repository(
        self,
        repo_path: str,
        changed_files: Optional[List[str]] = None,
        enabled_scanners: Optional[List[str]] = None,
    ) -> Tuple[List[NormalizedScanResult], List[ScannerExecutionSummary]]:
        """
        Executes configured static analysis scanners in parallel against a target repository.

        Args:
            repo_path: Absolute or resolvable path to repository workspace.
            changed_files: Optional list of relative paths for targeted diff scanning.
            enabled_scanners: Optional list of scanner names to restrict execution.

        Returns:
            Tuple of (all_findings, execution_summaries)
        """
        active_scanners: List[BaseScanner] = []
        target_names = set(enabled_scanners) if enabled_scanners else set(self._scanners.keys())

        for name, scanner in self._scanners.items():
            if name in target_names:
                active_scanners.append(scanner)

        if not active_scanners:
            logger.warning("No active scanners matched execution criteria")
            return [], []

        logger.info(
            f"Starting concurrent scan with {len(active_scanners)} scanners",
            extra={"scanners": [s.name for s in active_scanners], "repo": repo_path},
        )

        # Run all selected scanners concurrently with asyncio.gather
        tasks = [
            self._execute_single_scanner(scanner, repo_path, changed_files)
            for scanner in active_scanners
        ]
        results = await asyncio.gather(*tasks)

        all_findings: List[NormalizedScanResult] = []
        all_summaries: List[ScannerExecutionSummary] = []

        for scanner_name, findings, summary in results:
            all_findings.extend(findings)
            all_summaries.append(summary)

        logger.info(
            f"Scan completed: {len(all_findings)} total findings across {len(all_summaries)} tools",
            extra={
                "total_findings": len(all_findings),
                "successful_scanners": sum(1 for s in all_summaries if s.status == "SUCCESS"),
            },
        )

        return all_findings, all_summaries

    @staticmethod
    def filter_by_severity(
        findings: List[NormalizedScanResult],
        min_severity: ScannerSeverity,
    ) -> List[NormalizedScanResult]:
        """Filters findings to only include those at or above min_severity."""
        severity_rank = {
            ScannerSeverity.CRITICAL: 5,
            ScannerSeverity.HIGH: 4,
            ScannerSeverity.MEDIUM: 3,
            ScannerSeverity.LOW: 2,
            ScannerSeverity.INFO: 1,
        }
        threshold = severity_rank.get(min_severity, 1)
        return [f for f in findings if severity_rank.get(f.severity, 1) >= threshold]

    @staticmethod
    def filter_by_category(
        findings: List[NormalizedScanResult],
        category: ScannerCategory,
    ) -> List[NormalizedScanResult]:
        """Filters findings by functional category."""
        return [f for f in findings if f.category == category]

    @staticmethod
    def group_by_file(
        findings: List[NormalizedScanResult],
    ) -> Dict[str, List[NormalizedScanResult]]:
        """Groups findings by their relative file path."""
        grouped: Dict[str, List[NormalizedScanResult]] = {}
        for f in findings:
            grouped.setdefault(f.file_path, []).append(f)
        return grouped
