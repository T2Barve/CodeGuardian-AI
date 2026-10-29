import json
import os
import re
import shutil
from typing import Any, Dict, List, Optional

from app.scanners.base import BaseScanner
from app.schemas.scanner import NormalizedScanResult, ScannerCategory, ScannerSeverity
from app.utils.logging import get_logger

logger = get_logger("codeguardian.scanners.semgrep")

SEMGREP_RULES = [
    {
        "id": "semgrep.python.sqli.format",
        "lang": [".py"],
        "regex": re.compile(r"(?:SELECT|INSERT|UPDATE|DELETE)\s+.*(?:%s|\{[a-zA-Z0-9_]+\}|\+|format\(|\.format)", re.IGNORECASE),
        "title": "SQL Injection Vector via String Format / Concatenation",
        "message": "Raw SQL statement constructed via string concatenation or format string without parameterized query binding.",
        "category": ScannerCategory.SECURITY,
        "severity": ScannerSeverity.CRITICAL,
        "metadata": {"cwe": "CWE-89", "owasp": "A03:2021-Injection"},
    },
    {
        "id": "semgrep.python.command-injection",
        "lang": [".py"],
        "regex": re.compile(r"(?:os\.system|os\.popen|subprocess\.call|subprocess\.Popen)\s*\(.*(?:\+|format|%s)", re.IGNORECASE),
        "title": "Command Injection via Unsanitized System Invocation",
        "message": "System shell command constructed dynamically using string operations.",
        "category": ScannerCategory.SECURITY,
        "severity": ScannerSeverity.CRITICAL,
        "metadata": {"cwe": "CWE-78", "owasp": "A03:2021-Injection"},
    },
    {
        "id": "semgrep.js.dom-xss.innerhtml",
        "lang": [".js", ".jsx", ".ts", ".tsx"],
        "regex": re.compile(r"\.innerHTML\s*=\s*[^\"\']+", re.IGNORECASE),
        "title": "DOM-Based Cross-Site Scripting (XSS) via innerHTML",
        "message": "Assignment of dynamic or unsanitized content directly to innerHTML enables client-side XSS execution.",
        "category": ScannerCategory.SECURITY,
        "severity": ScannerSeverity.HIGH,
        "metadata": {"cwe": "CWE-79", "owasp": "A03:2021-Injection"},
    },
    {
        "id": "semgrep.generic.cors.wildcard",
        "lang": [".py", ".js", ".ts", ".json"],
        "regex": re.compile(r"[\'\"]Access-Control-Allow-Origin[\'\"]\s*[:,\s]\s*[\'\"]\*[\'\"]", re.IGNORECASE),
        "title": "Permissive Wildcard Cross-Origin Resource Sharing (CORS)",
        "message": "Access-Control-Allow-Origin header is set to wildcard '*', exposing sensitive APIs to arbitrary domains.",
        "category": ScannerCategory.SECURITY,
        "severity": ScannerSeverity.MEDIUM,
        "metadata": {"cwe": "CWE-942", "owasp": "A05:2021-Security Misconfiguration"},
    },
    {
        "id": "semgrep.python.unsafe-yaml-load",
        "lang": [".py"],
        "regex": re.compile(r"yaml\.load\s*\([^,)]+\)(?!\s*Loader=yaml\.SafeLoader)", re.IGNORECASE),
        "title": "Arbitrary Code Execution via Unsafe yaml.load()",
        "message": "Calling yaml.load() without SafeLoader allows arbitrary Python object instantiation and code execution.",
        "category": ScannerCategory.SECURITY,
        "severity": ScannerSeverity.HIGH,
        "metadata": {"cwe": "CWE-502", "owasp": "A08:2021-Software and Data Integrity Failures"},
    },
    {
        "id": "semgrep.python.tls.disabled-verification",
        "lang": [".py"],
        "regex": re.compile(r"(?:verify\s*=\s*False|check_hostname\s*=\s*False)", re.IGNORECASE),
        "title": "Insecure TLS/SSL Certificate Verification Disabled",
        "message": "Disabling TLS certificate verification allows Man-in-the-Middle (MitM) attacks.",
        "category": ScannerCategory.SECURITY,
        "severity": ScannerSeverity.HIGH,
        "metadata": {"cwe": "CWE-295", "owasp": "A07:2021-Identification and Authentication Failures"},
    },
]


class SemgrepScanner(BaseScanner):
    """Semgrep SAST adapter for polyglot semantic rule pattern matching."""

    def __init__(self, timeout_seconds: Optional[int] = None):
        super().__init__(name="semgrep", timeout_seconds=timeout_seconds)

    def is_available(self) -> bool:
        return True

    async def scan(
        self, repo_path: str, changed_files: Optional[List[str]] = None
    ) -> List[NormalizedScanResult]:
        valid_root = self._validate_workspace_path(repo_path)
        semgrep_bin = shutil.which("semgrep")

        # 1. Attempt Semgrep CLI if installed
        if semgrep_bin:
            try:
                cmd = [semgrep_bin, "scan", "--json", "--quiet", "--config", "auto", valid_root]
                exit_code, stdout, stderr = await self._run_subprocess(cmd, cwd=valid_root)
                if stdout.strip():
                    return self._parse_semgrep_json(stdout, valid_root)
            except Exception as exc:
                logger.warning(
                    "Semgrep CLI execution failed or timed out; using rule pattern engine",
                    extra={"error": str(exc)},
                )

        # 2. Native polyglot pattern engine
        return self._scan_with_rule_engine(valid_root, changed_files)

    def _scan_with_rule_engine(
        self, root_dir: str, changed_files: Optional[List[str]] = None
    ) -> List[NormalizedScanResult]:
        results: List[NormalizedScanResult] = []

        target_files: List[str] = []
        if changed_files:
            for f in changed_files:
                safe_p = self._validate_relative_file_path(root_dir, f)
                if os.path.exists(safe_p) and os.path.isfile(safe_p):
                    target_files.append(safe_p)
        else:
            for dirpath, _, filenames in os.walk(root_dir):
                # Skip hidden and dependency directories
                if "/." in dirpath.replace("\\", "/") or "\\." in dirpath or "node_modules" in dirpath:
                    continue
                for fname in filenames:
                    target_files.append(os.path.join(dirpath, fname))

        for file_path in target_files:
            ext = os.path.splitext(file_path)[1].lower()
            rel_path = os.path.relpath(file_path, root_dir).replace("\\", "/")

            applicable_rules = [r for r in SEMGREP_RULES if ext in r["lang"]]
            if not applicable_rules:
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()

                for line_idx, line in enumerate(lines, start=1):
                    for rule in applicable_rules:
                        if rule["regex"].search(line):
                            results.append(
                                NormalizedScanResult(
                                    scanner="semgrep",
                                    rule_id=rule["id"],
                                    category=rule["category"],
                                    severity=rule["severity"],
                                    confidence=0.92,
                                    file_path=rel_path,
                                    line_start=line_idx,
                                    line_end=line_idx,
                                    title=rule["title"],
                                    message=rule["message"],
                                    code_snippet=line.strip(),
                                    raw_output={"rule_id": rule["id"], "line": line_idx},
                                    metadata=rule["metadata"],
                                )
                            )
            except Exception as exc:
                logger.error(f"Error scanning {file_path} in Semgrep engine", extra={"error": str(exc)})

        return results

    def _parse_semgrep_json(self, raw_json: str, root_dir: str) -> List[NormalizedScanResult]:
        results: List[NormalizedScanResult] = []
        try:
            data = json.loads(raw_json)
            for item in data.get("results", []):
                file_name = item.get("path", "")
                rel_path = os.path.relpath(file_name, root_dir).replace("\\", "/")
                rule_id = item.get("check_id", "semgrep-rule")
                extra = item.get("extra", {})
                raw_severity = extra.get("severity", "WARNING").upper()

                severity = ScannerSeverity.MEDIUM
                if raw_severity == "ERROR":
                    severity = ScannerSeverity.HIGH
                elif raw_severity == "CRITICAL":
                    severity = ScannerSeverity.CRITICAL
                elif raw_severity == "INFO":
                    severity = ScannerSeverity.INFO

                start_line = item.get("start", {}).get("line")
                end_line = item.get("end", {}).get("line")

                results.append(
                    NormalizedScanResult(
                        scanner="semgrep",
                        rule_id=rule_id,
                        category=ScannerCategory.SECURITY,
                        severity=severity,
                        confidence=0.92,
                        file_path=rel_path,
                        line_start=start_line,
                        line_end=end_line,
                        title=f"Semgrep: {rule_id.split('.')[-1].replace('-', ' ').title()}",
                        message=extra.get("message", ""),
                        code_snippet=extra.get("lines", "").strip(),
                        raw_output=item,
                        metadata=extra.get("metadata", {}),
                    )
                )
        except Exception as exc:
            logger.error("Failed to parse Semgrep JSON output", extra={"error": str(exc)})
        return results
