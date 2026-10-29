"""
CodeGuardian AI — Static Analysis Scanner Subsystem
Provides adapters and orchestrator for Bandit, Semgrep, Gitleaks, and ESLint.
"""

from app.scanners.bandit import BanditASTAnalyzer, BanditScanner
from app.scanners.base import BaseScanner, ScannerExecutionError, ScannerTimeoutError
from app.scanners.eslint import ESLintScanner
from app.scanners.gitleaks import GitleaksScanner, calculate_shannon_entropy, mask_secret
from app.scanners.runner import ScannerEngine
from app.scanners.semgrep import SemgrepScanner
from app.schemas.scanner import (
    NormalizedScanResult,
    ScannerCategory,
    ScannerExecutionSummary,
    ScannerSeverity,
)

__all__ = [
    "BaseScanner",
    "ScannerTimeoutError",
    "ScannerExecutionError",
    "BanditScanner",
    "BanditASTAnalyzer",
    "SemgrepScanner",
    "GitleaksScanner",
    "calculate_shannon_entropy",
    "mask_secret",
    "ESLintScanner",
    "ScannerEngine",
    "NormalizedScanResult",
    "ScannerCategory",
    "ScannerSeverity",
    "ScannerExecutionSummary",
]
