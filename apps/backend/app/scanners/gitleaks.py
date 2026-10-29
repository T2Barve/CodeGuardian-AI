import json
import math
import os
import re
import shutil
from typing import Any, Dict, List, Optional

from app.scanners.base import BaseScanner
from app.schemas.scanner import NormalizedScanResult, ScannerCategory, ScannerSeverity
from app.utils.logging import get_logger

logger = get_logger("codeguardian.scanners.gitleaks")

# Secret signature regex patterns based on Gitleaks official ruleset
GITLEAKS_PATTERNS = [
    {
        "id": "aws-access-token",
        "name": "AWS Access Key ID",
        "regex": re.compile(r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"),
        "severity": ScannerSeverity.CRITICAL,
    },
    {
        "id": "github-pat",
        "name": "GitHub Personal Access Token",
        "regex": re.compile(r"(?:gh[pousr]_[A-Za-z0-9_]{36,255}|github_pat_[a-zA-Z0-9_]{22,})"),
        "severity": ScannerSeverity.CRITICAL,
    },
    {
        "id": "private-key",
        "name": "Asymmetric Private Key",
        "regex": re.compile(r"-----BEGIN (?:(?:RSA|EC|DSA|OPENSSH) )?PRIVATE KEY-----"),
        "severity": ScannerSeverity.CRITICAL,
    },
    {
        "id": "slack-token",
        "name": "Slack App/User Token",
        "regex": re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,48}"),
        "severity": ScannerSeverity.HIGH,
    },
    {
        "id": "jwt-token",
        "name": "JSON Web Token (JWT) in Plaintext",
        "regex": re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),
        "severity": ScannerSeverity.HIGH,
    },
    {
        "id": "generic-api-key",
        "name": "Generic High-Entropy Secret/API Key",
        "regex": re.compile(r"(?i)(?:api_key|apikey|secret_key|private_key|auth_token)\s*[:=]\s*['\"]([a-zA-Z0-9_\-\.]{24,})['\"]"),
        "severity": ScannerSeverity.HIGH,
    },
    {
        "id": "db-connection-secret",
        "name": "Database Connection String with Credentials",
        "regex": re.compile(r"(?:postgres|postgresql|mysql|mongodb|redis):\/\/[a-zA-Z0-9_-]+:([^@\s]{6,})@[a-zA-Z0-9_\.-]+"),
        "severity": ScannerSeverity.CRITICAL,
    },
]

# File extensions to ignore during secret scanning (binaries, locks, etc.)
IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2",
    ".pyc", ".pyo", ".pyd", ".db", ".sqlite", ".sqlite3", ".bin",
}


def calculate_shannon_entropy(data: str) -> float:
    """Calculates Shannon entropy to detect high-randomness secret strings."""
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    for x in set(data):
        p_x = float(data.count(x)) / length
        entropy += - p_x * math.log(p_x, 2)
    return entropy


def mask_secret(secret_text: str) -> str:
    """Masks secret characters for safe presentation in logs and reports."""
    if len(secret_text) <= 6:
        return "***REDACTED***"
    return secret_text[:3] + "*" * (len(secret_text) - 6) + secret_text[-3:]


class GitleaksScanner(BaseScanner):
    """Gitleaks SAST adapter for high-entropy credential and secret leak detection."""

    def __init__(self, timeout_seconds: Optional[int] = None):
        super().__init__(name="gitleaks", timeout_seconds=timeout_seconds)

    def is_available(self) -> bool:
        return True

    async def scan(
        self, repo_path: str, changed_files: Optional[List[str]] = None
    ) -> List[NormalizedScanResult]:
        valid_root = self._validate_workspace_path(repo_path)
        gitleaks_bin = shutil.which("gitleaks")

        # 1. Attempt official CLI if available
        if gitleaks_bin:
            try:
                cmd = [gitleaks_bin, "detect", "--no-git", "--source", valid_root, "-f", "json", "-v"]
                exit_code, stdout, stderr = await self._run_subprocess(cmd, cwd=valid_root)
                if stdout.strip():
                    return self._parse_gitleaks_json(stdout, valid_root)
            except Exception as exc:
                logger.warning(
                    "Gitleaks CLI execution failed or timed out; using pattern scanner",
                    extra={"error": str(exc)},
                )

        # 2. Native regex and entropy scanner
        return self._scan_with_pattern_engine(valid_root, changed_files)

    def _scan_with_pattern_engine(
        self, root_dir: str, changed_files: Optional[List[str]] = None
    ) -> List[NormalizedScanResult]:
        results: List[NormalizedScanResult] = []

        # Target files
        target_paths: List[str] = []
        if changed_files:
            for f in changed_files:
                full_p = self._validate_relative_file_path(root_dir, f)
                if os.path.exists(full_p) and os.path.isfile(full_p):
                    target_paths.append(full_p)
        else:
            for dirpath, _, filenames in os.walk(root_dir):
                # Skip hidden directories like .git
                if "/." in dirpath.replace("\\", "/") or "\\." in dirpath:
                    continue
                for fname in filenames:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in IGNORED_EXTENSIONS:
                        target_paths.append(os.path.join(dirpath, fname))

        for file_path in target_paths:
            rel_path = os.path.relpath(file_path, root_dir).replace("\\", "/")
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()

                for line_idx, line in enumerate(lines, start=1):
                    for pattern in GITLEAKS_PATTERNS:
                        match = pattern["regex"].search(line)
                        if match:
                            matched_text = match.group(0)
                            # Verify minimum entropy for generic API keys
                            if pattern["id"] == "generic-api-key":
                                secret_candidate = match.group(1) if match.groups() else matched_text
                                if calculate_shannon_entropy(secret_candidate) < 3.0:
                                    continue

                            redacted_snippet = line.strip().replace(
                                matched_text, mask_secret(matched_text)
                            )

                            results.append(
                                NormalizedScanResult(
                                    scanner="gitleaks",
                                    rule_id=pattern["id"],
                                    category=ScannerCategory.SECRET,
                                    severity=pattern["severity"],
                                    confidence=0.98,
                                    file_path=rel_path,
                                    line_start=line_idx,
                                    line_end=line_idx,
                                    title=f"Secret Detected: {pattern['name']}",
                                    message=(
                                        f"High-entropy secret pattern matching '{pattern['name']}' "
                                        f"was identified in plain text."
                                    ),
                                    code_snippet=redacted_snippet,
                                    raw_output={
                                        "pattern_id": pattern["id"],
                                        "line_number": line_idx,
                                        "entropy": round(calculate_shannon_entropy(matched_text), 2),
                                    },
                                    metadata={
                                        "cwe": "CWE-798",
                                        "owasp": "A07:2021-Identification and Authentication Failures",
                                        "entropy": round(calculate_shannon_entropy(matched_text), 2),
                                    },
                                )
                            )
            except Exception as exc:
                logger.error(f"Error scanning file for secrets: {file_path}", extra={"error": str(exc)})

        return results

    def _parse_gitleaks_json(self, raw_json: str, root_dir: str) -> List[NormalizedScanResult]:
        results: List[NormalizedScanResult] = []
        try:
            data = json.loads(raw_json)
            for item in data:
                file_name = item.get("File", "")
                rel_path = os.path.relpath(file_name, root_dir).replace("\\", "/")
                rule_id = item.get("RuleID", "generic-secret")
                line_no = item.get("StartLine", 1)
                secret = item.get("Secret", "")
                masked_secret = mask_secret(secret)

                results.append(
                    NormalizedScanResult(
                        scanner="gitleaks",
                        rule_id=rule_id,
                        category=ScannerCategory.SECRET,
                        severity=ScannerSeverity.CRITICAL,
                        confidence=0.99,
                        file_path=rel_path,
                        line_start=line_no,
                        line_end=item.get("EndLine", line_no),
                        title=f"Leaked Credential: {item.get('Description', rule_id)}",
                        message=f"Hardcoded secret detected matching rule '{rule_id}'.",
                        code_snippet=f"{item.get('Match', '')}".replace(secret, masked_secret).strip(),
                        raw_output=item,
                        metadata={
                            "cwe": "CWE-798",
                            "entropy": item.get("Entropy", 0.0),
                            "commit": item.get("Commit", ""),
                        },
                    )
                )
        except Exception as exc:
            logger.error("Failed to parse Gitleaks JSON report", extra={"error": str(exc)})
        return results
