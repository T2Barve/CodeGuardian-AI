import json
import os
import re
import shutil
from typing import Any, Dict, List, Optional

from app.scanners.base import BaseScanner
from app.schemas.scanner import NormalizedScanResult, ScannerCategory, ScannerSeverity
from app.utils.logging import get_logger

logger = get_logger("codeguardian.scanners.eslint")

JS_SECURITY_RULES = [
    {
        "id": "security/detect-eval-with-expression",
        "regex": re.compile(r"\beval\s*\([^)]+\)"),
        "title": "Unsafe Dynamic Code Execution via eval()",
        "message": "Usage of eval() with dynamic expressions allows arbitrary code execution (CWE-95).",
        "severity": ScannerSeverity.CRITICAL,
        "category": ScannerCategory.SECURITY,
        "metadata": {"cwe": "CWE-95", "owasp": "A03:2021-Injection"},
    },
    {
        "id": "security/detect-document-write",
        "regex": re.compile(r"document\.write(?:ln)?\s*\([^)]+\)"),
        "title": "Cross-Site Scripting via document.write()",
        "message": "Writing unencoded content directly via document.write allows client-side script injection.",
        "severity": ScannerSeverity.HIGH,
        "category": ScannerCategory.SECURITY,
        "metadata": {"cwe": "CWE-79", "owasp": "A03:2021-Injection"},
    },
    {
        "id": "security/detect-innerhtml-assignment",
        "regex": re.compile(r"\.innerHTML\s*=\s*[^\"\']+", re.IGNORECASE),
        "title": "DOM-Based Cross-Site Scripting via innerHTML",
        "message": "Assigning unsanitized dynamic data to innerHTML leads to client-side XSS.",
        "severity": ScannerSeverity.HIGH,
        "category": ScannerCategory.SECURITY,
        "metadata": {"cwe": "CWE-79", "owasp": "A03:2021-Injection"},
    },
    {
        "id": "security/detect-insecure-storage",
        "regex": re.compile(r"localStorage\.(?:setItem|getItem)\s*\(\s*['\"](?:auth_token|token|password|jwt|secret)", re.IGNORECASE),
        "title": "Sensitive Token Stored in Insecure Web Storage",
        "message": "Storing sensitive credentials or authentication tokens in localStorage exposes them to XSS exfiltration.",
        "severity": ScannerSeverity.MEDIUM,
        "category": ScannerCategory.SECURITY,
        "metadata": {"cwe": "CWE-922", "owasp": "A04:2021-Insecure Design"},
    },
    {
        "id": "security/detect-function-constructor",
        "regex": re.compile(r"new\s+Function\s*\([^)]+\)"),
        "title": "Dynamic Code Construction via Function()",
        "message": "Using the Function() constructor compiles strings into executable code, analogous to eval().",
        "severity": ScannerSeverity.HIGH,
        "category": ScannerCategory.SECURITY,
        "metadata": {"cwe": "CWE-95", "owasp": "A03:2021-Injection"},
    },
    {
        "id": "quality/no-console-log",
        "regex": re.compile(r"console\.log\s*\([^)]+\)"),
        "title": "Production Console Logging Detected",
        "message": "console.log statements left in production code may leak sensitive application state.",
        "severity": ScannerSeverity.INFO,
        "category": ScannerCategory.QUALITY,
        "metadata": {"rule": "no-console"},
    },
]


class ESLintScanner(BaseScanner):
    """ESLint SAST adapter for JavaScript and TypeScript quality & security linting."""

    def __init__(self, timeout_seconds: Optional[int] = None):
        super().__init__(name="eslint", timeout_seconds=timeout_seconds)

    def is_available(self) -> bool:
        return True

    async def scan(
        self, repo_path: str, changed_files: Optional[List[str]] = None
    ) -> List[NormalizedScanResult]:
        valid_root = self._validate_workspace_path(repo_path)
        eslint_bin = shutil.which("eslint")

        # 1. Attempt ESLint CLI if installed
        if eslint_bin:
            try:
                cmd = [eslint_bin, "--format", "json", valid_root]
                exit_code, stdout, stderr = await self._run_subprocess(cmd, cwd=valid_root)
                if stdout.strip():
                    return self._parse_eslint_json(stdout, valid_root)
            except Exception as exc:
                logger.warning(
                    "ESLint CLI execution failed or timed out; falling back to pattern linter",
                    extra={"error": str(exc)},
                )

        # 2. Native JS/TS rule analyzer
        return self._scan_with_pattern_linter(valid_root, changed_files)

    def _scan_with_pattern_linter(
        self, root_dir: str, changed_files: Optional[List[str]] = None
    ) -> List[NormalizedScanResult]:
        results: List[NormalizedScanResult] = []
        js_extensions = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}

        target_files: List[str] = []
        if changed_files:
            for f in changed_files:
                ext = os.path.splitext(f)[1].lower()
                if ext in js_extensions:
                    safe_p = self._validate_relative_file_path(root_dir, f)
                    if os.path.exists(safe_p):
                        target_files.append(safe_p)
        else:
            for dirpath, _, filenames in os.walk(root_dir):
                # Skip node_modules, build directories, and hidden folders
                if "node_modules" in dirpath or "dist" in dirpath or "/." in dirpath.replace("\\", "/"):
                    continue
                for fname in filenames:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in js_extensions:
                        target_files.append(os.path.join(dirpath, fname))

        for file_path in target_files:
            rel_path = os.path.relpath(file_path, root_dir).replace("\\", "/")
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()

                for line_idx, line in enumerate(lines, start=1):
                    for rule in JS_SECURITY_RULES:
                        if rule["regex"].search(line):
                            results.append(
                                NormalizedScanResult(
                                    scanner="eslint",
                                    rule_id=rule["id"],
                                    category=rule["category"],
                                    severity=rule["severity"],
                                    confidence=0.90,
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
                logger.error(f"Error linting {file_path} in ESLint engine", extra={"error": str(exc)})

        return results

    def _parse_eslint_json(self, raw_json: str, root_dir: str) -> List[NormalizedScanResult]:
        results: List[NormalizedScanResult] = []
        try:
            data = json.loads(raw_json)
            for file_entry in data:
                file_path = file_entry.get("filePath", "")
                rel_path = os.path.relpath(file_path, root_dir).replace("\\", "/")

                for msg in file_entry.get("messages", []):
                    rule_id = msg.get("ruleId") or "eslint-violation"
                    eslint_severity = msg.get("severity", 1)  # 1 = warning, 2 = error

                    severity = ScannerSeverity.MEDIUM if eslint_severity == 1 else ScannerSeverity.HIGH
                    category = ScannerCategory.SECURITY if "security" in rule_id else ScannerCategory.QUALITY

                    results.append(
                        NormalizedScanResult(
                            scanner="eslint",
                            rule_id=rule_id,
                            category=category,
                            severity=severity,
                            confidence=0.92,
                            file_path=rel_path,
                            line_start=msg.get("line"),
                            line_end=msg.get("endLine", msg.get("line")),
                            title=f"ESLint: {rule_id}",
                            message=msg.get("message", ""),
                            code_snippet=None,
                            raw_output=msg,
                            metadata={"fatal": msg.get("fatal", False)},
                        )
                    )
        except Exception as exc:
            logger.error("Failed to parse ESLint JSON output", extra={"error": str(exc)})
        return results
