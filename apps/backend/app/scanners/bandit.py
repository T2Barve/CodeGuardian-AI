import ast
import json
import os
import shutil
from typing import Any, Dict, List, Optional

from app.scanners.base import BaseScanner
from app.schemas.scanner import NormalizedScanResult, ScannerCategory, ScannerSeverity
from app.utils.logging import get_logger

logger = get_logger("codeguardian.scanners.bandit")


class BanditASTAnalyzer(ast.NodeVisitor):
    """
    Python AST-based security analyzer implementing core Bandit checks (B608, B602, B303, B105, B301)
    to provide deterministic security analysis when the standalone bandit CLI is not present.
    """

    def __init__(self, file_path: str, repo_root: str):
        self.file_path = file_path
        self.repo_root = repo_root
        self.rel_path = os.path.relpath(file_path, repo_root).replace("\\", "/")
        self.findings: List[NormalizedScanResult] = []
        self.dynamic_sql_vars: set = set()

    def _is_dynamic_sql(self, node: ast.AST) -> bool:
        """Determines if an AST node constructs dynamic SQL via concatenation, formatting, or f-strings."""
        sql_keywords = ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "FROM ", "WHERE ", "DROP ", "ALTER ")
        if isinstance(node, ast.JoinedStr):
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    if any(kw in part.value.upper() for kw in sql_keywords):
                        return True
            # Any f-string passed directly to execute() is suspect
            return True
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
            left_val = getattr(node.left, "value", "") if isinstance(node.left, ast.Constant) else ""
            if any(kw in str(left_val).upper() for kw in sql_keywords):
                return True
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            base_val = getattr(node.func.value, "value", "") if isinstance(node.func.value, ast.Constant) else ""
            if any(kw in str(base_val).upper() for kw in sql_keywords):
                return True
        return False

    def visit_Call(self, node: ast.Call):
        # 1. Check B608: SQL Injection via execute() with dynamic string formatting
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name in ("execute", "executemany", "raw_sql", "cursor_execute") and node.args:
            first_arg = node.args[0]
            is_dynamic_sql = (
                self._is_dynamic_sql(first_arg)
                or (isinstance(first_arg, ast.Name) and first_arg.id in self.dynamic_sql_vars)
            )
            if is_dynamic_sql:
                self.findings.append(
                    NormalizedScanResult(
                        scanner="bandit",
                        rule_id="B608",
                        category=ScannerCategory.SECURITY,
                        severity=ScannerSeverity.CRITICAL,
                        confidence=0.95,
                        file_path=self.rel_path,
                        line_start=node.lineno,
                        line_end=getattr(node, "end_lineno", node.lineno),
                        title="Possible SQL Injection via String Construction",
                        message="Potential SQL injection detected: untrusted input directly formatted into raw database query.",
                        code_snippet=None,
                        raw_output={"rule": "B608", "lineno": node.lineno, "func": func_name},
                        metadata={
                            "cwe": "CWE-89",
                            "owasp": "A03:2021-Injection",
                            "test_name": "hardcoded_sql_expressions",
                        },
                    )
                )

        # 2. Check B602 / B603: Subprocess with shell=True
        if func_name in ("Popen", "run", "call", "check_call", "check_output"):
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                    self.findings.append(
                        NormalizedScanResult(
                            scanner="bandit",
                            rule_id="B602",
                            category=ScannerCategory.SECURITY,
                            severity=ScannerSeverity.CRITICAL,
                            confidence=0.98,
                            file_path=self.rel_path,
                            line_start=node.lineno,
                            line_end=getattr(node, "end_lineno", node.lineno),
                            title="Subprocess Call with shell=True (Command Injection)",
                            message="Invocation of subprocess with shell=True opens the application to remote command execution.",
                            code_snippet=None,
                            metadata={"cwe": "CWE-78", "owasp": "A03:2021-Injection"},
                        )
                    )

        # 3. Check B303: Insecure MD5 / SHA1 usage
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "hashlib"
            and node.func.attr in ("md5", "sha1")
        ):
            self.findings.append(
                NormalizedScanResult(
                    scanner="bandit",
                    rule_id="B303",
                    category=ScannerCategory.SECURITY,
                    severity=ScannerSeverity.MEDIUM,
                    confidence=0.90,
                    file_path=self.rel_path,
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    title=f"Use of Insecure Hash Algorithm ({node.func.attr.upper()})",
                    message=f"Cryptographic hash '{node.func.attr}' is cryptographically broken and vulnerable to collision attacks.",
                    code_snippet=None,
                    metadata={"cwe": "CWE-327", "owasp": "A02:2021-Cryptographic Failures"},
                )
            )

        # 4. Check B301: Insecure pickle deserialization
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "pickle"
            and node.func.attr in ("load", "loads")
        ):
            self.findings.append(
                NormalizedScanResult(
                    scanner="bandit",
                    rule_id="B301",
                    category=ScannerCategory.SECURITY,
                    severity=ScannerSeverity.CRITICAL,
                    confidence=0.95,
                    file_path=self.rel_path,
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    title="Insecure Deserialization via Pickle",
                    message="Pickle deserialization of untrusted data allows arbitrary code execution.",
                    code_snippet=None,
                    metadata={"cwe": "CWE-502", "owasp": "A08:2021-Software and Data Integrity Failures"},
                )
            )

        # 5. Check B506: Insecure yaml.load without SafeLoader
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "yaml"
            and node.func.attr == "load"
        ):
            has_safe_loader = any(
                (keyword.arg == "Loader" and "Safe" in ast.dump(keyword.value))
                for keyword in node.keywords
            )
            if not has_safe_loader:
                self.findings.append(
                    NormalizedScanResult(
                        scanner="bandit",
                        rule_id="B506",
                        category=ScannerCategory.SECURITY,
                        severity=ScannerSeverity.HIGH,
                        confidence=0.95,
                        file_path=self.rel_path,
                        line_start=node.lineno,
                        line_end=getattr(node, "end_lineno", node.lineno),
                        title="Insecure YAML Loading via yaml.load()",
                        message="Calling yaml.load() without Loader=yaml.SafeLoader allows arbitrary code execution.",
                        code_snippet=None,
                        raw_output={"rule": "B506", "lineno": node.lineno, "func": "yaml.load"},
                        metadata={"cwe": "CWE-502", "owasp": "A08:2021-Software and Data Integrity Failures"},
                    )
                )

        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert):
        # 6. Check B101: Use of assert in production code
        if not ("test" in self.rel_path.lower() or "conftest" in self.rel_path.lower()):
            self.findings.append(
                NormalizedScanResult(
                    scanner="bandit",
                    rule_id="B101",
                    category=ScannerCategory.QUALITY,
                    severity=ScannerSeverity.LOW,
                    confidence=0.85,
                    file_path=self.rel_path,
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    title="Use of assert detected in production code",
                    message="assert statements are removed when running Python with -O flag; do not rely on them for logic validation.",
                    code_snippet=None,
                    raw_output={"rule": "B101", "lineno": node.lineno},
                    metadata={"cwe": "CWE-617", "owasp": "A04:2021-Insecure Design"},
                )
            )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # Track variables holding dynamic SQL expressions (e.g. query = f"SELECT ...")
        if self._is_dynamic_sql(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.dynamic_sql_vars.add(target.id)

        # 7. Check B105: Hardcoded credentials
        for target in node.targets:
            if isinstance(target, ast.Name):
                name_lower = target.id.lower()
                if any(k in name_lower for k in ("password", "secret_key", "api_token", "auth_token", "api_key")):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        val = node.value.value
                        if len(val) >= 6 and not val.startswith(("${", "{", "YOUR_")):
                            masked_val = val[:2] + "*" * (len(val) - 4) + val[-2:] if len(val) > 4 else "******"
                            self.findings.append(
                                NormalizedScanResult(
                                    scanner="bandit",
                                    rule_id="B105",
                                    category=ScannerCategory.SECRET,
                                    severity=ScannerSeverity.HIGH,
                                    confidence=0.85,
                                    file_path=self.rel_path,
                                    line_start=node.lineno,
                                    line_end=getattr(node, "end_lineno", node.lineno),
                                    title="Possible Hardcoded Password or Secret String",
                                    message=f"Hardcoded sensitive credential identified in variable assignment '{target.id}'.",
                                    code_snippet=None,
                                    raw_output={"rule": "B105", "variable": target.id, "masked_preview": masked_val},
                                    metadata={"cwe": "CWE-798", "owasp": "A07:2021-Identification and Authentication Failures"},
                                )
                            )
        self.generic_visit(node)


class BanditScanner(BaseScanner):
    """Bandit SAST adapter for AST-level Python security vulnerability scanning."""

    def __init__(self, timeout_seconds: Optional[int] = None):
        super().__init__(name="bandit", timeout_seconds=timeout_seconds)

    def is_available(self) -> bool:
        return True  # Native AST analyzer is always available; binary used if installed

    async def scan(
        self, repo_path: str, changed_files: Optional[List[str]] = None
    ) -> List[NormalizedScanResult]:
        valid_root = self._validate_workspace_path(repo_path)
        bandit_binary = shutil.which("bandit")

        # 1. Attempt CLI execution if binary is installed
        if bandit_binary:
            try:
                cmd = [bandit_binary, "-f", "json", "-q"]
                if changed_files:
                    target_files = [
                        self._validate_relative_file_path(valid_root, f)
                        for f in changed_files
                        if f.endswith(".py") and os.path.exists(self._validate_relative_file_path(valid_root, f))
                    ]
                    if not target_files:
                        return []
                    cmd.extend(target_files)
                else:
                    cmd.extend(["-r", valid_root])

                exit_code, stdout, stderr = await self._run_subprocess(cmd, cwd=valid_root)
                if stdout.strip():
                    return self._parse_bandit_json(stdout, valid_root)
            except Exception as exc:
                logger.warning(
                    "Bandit CLI execution failed or timed out; falling back to AST engine",
                    extra={"error": str(exc)},
                )

        # 2. Native AST Analyzer execution
        return self._scan_with_ast_engine(valid_root, changed_files)

    def _scan_with_ast_engine(
        self, root_dir: str, changed_files: Optional[List[str]] = None
    ) -> List[NormalizedScanResult]:
        results: List[NormalizedScanResult] = []

        # Collect target Python files
        py_files: List[str] = []
        if changed_files:
            for f in changed_files:
                if f.endswith(".py"):
                    full_p = self._validate_relative_file_path(root_dir, f)
                    if os.path.exists(full_p):
                        py_files.append(full_p)
        else:
            for dirpath, _, filenames in os.walk(root_dir):
                # Skip hidden directories and virtualenvs
                if "/." in dirpath.replace("\\", "/") or "\\." in dirpath or "site-packages" in dirpath:
                    continue
                for filename in filenames:
                    if filename.endswith(".py"):
                        py_files.append(os.path.join(dirpath, filename))

        for file_path in py_files:
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    source_code = f.read()
                tree = ast.parse(source_code, filename=file_path)
                analyzer = BanditASTAnalyzer(file_path=file_path, repo_root=root_dir)
                analyzer.visit(tree)

                for finding in analyzer.findings:
                    finding.code_snippet = self._read_code_snippet(
                        file_path, finding.line_start, finding.line_end
                    )
                    results.append(finding)
            except SyntaxError as exc:
                logger.warning(f"Syntax error parsing {file_path} in AST scanner", extra={"error": str(exc)})
            except Exception as exc:
                logger.error(f"Unexpected error analyzing {file_path}", extra={"error": str(exc)})

        return results

    def _parse_bandit_json(self, raw_json: str, root_dir: str) -> List[NormalizedScanResult]:
        results: List[NormalizedScanResult] = []
        try:
            data = json.loads(raw_json)
            bandit_results = data.get("results", [])

            severity_map = {
                "HIGH": ScannerSeverity.CRITICAL,
                "MEDIUM": ScannerSeverity.HIGH,
                "LOW": ScannerSeverity.MEDIUM,
            }

            for item in bandit_results:
                filename = item.get("filename", "")
                rel_path = os.path.relpath(filename, root_dir).replace("\\", "/")
                test_id = item.get("test_id", "UNKNOWN")
                raw_severity = item.get("issue_severity", "MEDIUM")
                severity = severity_map.get(raw_severity, ScannerSeverity.MEDIUM)

                results.append(
                    NormalizedScanResult(
                        scanner="bandit",
                        rule_id=test_id,
                        category=ScannerCategory.SECURITY,
                        severity=severity,
                        confidence=0.95,
                        file_path=rel_path,
                        line_start=item.get("line_number"),
                        line_end=item.get("line_range", [item.get("line_number")])[-1],
                        title=f"Bandit {test_id}: {item.get('test_name', 'Security Issue')}",
                        message=item.get("issue_text", ""),
                        code_snippet=item.get("code", "").strip(),
                        raw_output=item,
                        metadata={
                            "cwe": item.get("issue_cwe", {}).get("link", ""),
                            "confidence": item.get("issue_confidence", ""),
                        },
                    )
                )
        except Exception as exc:
            logger.error("Failed to parse Bandit JSON output", extra={"error": str(exc)})
        return results
