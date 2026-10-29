import asyncio
import json
import os
import tempfile
import pytest
from typing import List

from app.scanners.bandit import BanditASTAnalyzer, BanditScanner
from app.scanners.base import BaseScanner, ScannerExecutionError, ScannerTimeoutError
from app.scanners.eslint import ESLintScanner
from app.scanners.gitleaks import (
    GitleaksScanner,
    calculate_shannon_entropy,
    mask_secret,
)
from app.scanners.runner import ScannerEngine
from app.scanners.semgrep import SemgrepScanner
from app.schemas.scanner import (
    NormalizedScanResult,
    ScannerCategory,
    ScannerExecutionSummary,
    ScannerSeverity,
)


@pytest.fixture
def temp_workspace():
    """Creates a clean temporary workspace for scanning tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir


# ==============================================================================
# 1. BANDIT SCANNER TESTS (AST & CLI)
# ==============================================================================


@pytest.mark.asyncio
async def test_bandit_ast_sql_injection(temp_workspace):
    """Verifies Bandit AST detection of SQL injection via dynamic string formatting (B608)."""
    vuln_code = (
        "def query_user(user_id):\n"
        "    query = f'SELECT * FROM users WHERE id = {user_id}'\n"
        "    db.execute(query)\n"
    )
    file_path = os.path.join(temp_workspace, "vuln_sql.py")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(vuln_code)

    scanner = BanditScanner()
    findings = await scanner.scan(temp_workspace, changed_files=["vuln_sql.py"])

    assert len(findings) >= 1
    b608 = next((f for f in findings if f.rule_id == "B608"), None)
    assert b608 is not None
    assert b608.severity == ScannerSeverity.CRITICAL
    assert b608.category == ScannerCategory.SECURITY
    assert b608.line_start == 3
    assert "SQL" in b608.title


@pytest.mark.asyncio
async def test_bandit_ast_command_injection_and_hashes(temp_workspace):
    """Verifies Bandit AST detection of subprocess shell=True (B602) and weak hashes (B303)."""
    vuln_code = (
        "import subprocess\n"
        "import hashlib\n"
        "def run_cmd(user_input):\n"
        "    subprocess.run('ls ' + user_input, shell=True)\n"
        "    digest = hashlib.md5(b'data').hexdigest()\n"
        "    return digest\n"
    )
    file_path = os.path.join(temp_workspace, "vuln_cmd.py")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(vuln_code)

    scanner = BanditScanner()
    findings = await scanner.scan(temp_workspace, changed_files=["vuln_cmd.py"])

    rule_ids = {f.rule_id for f in findings}
    assert "B602" in rule_ids  # shell=True
    assert "B303" in rule_ids  # MD5 usage


@pytest.mark.asyncio
async def test_bandit_ast_unsafe_yaml_and_pickle(temp_workspace):
    """Verifies Bandit AST detection of unsafe yaml.load (B506) and pickle (B301)."""
    vuln_code = (
        "import yaml\n"
        "import pickle\n"
        "def load_payload(raw):\n"
        "    y = yaml.load(raw)\n"
        "    p = pickle.loads(raw)\n"
        "    return y, p\n"
    )
    file_path = os.path.join(temp_workspace, "vuln_deserial.py")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(vuln_code)

    scanner = BanditScanner()
    findings = await scanner.scan(temp_workspace)

    rule_ids = {f.rule_id for f in findings}
    assert "B506" in rule_ids
    assert "B301" in rule_ids


@pytest.mark.asyncio
async def test_bandit_ast_hardcoded_secret_and_clean_file(temp_workspace):
    """Verifies Bandit secret detection and verifies clean code produces zero findings."""
    vuln_code = "auth_token = 'supersecretapikey12345'\n"
    clean_code = "def add(a, b):\n    return a + b\n"

    with open(os.path.join(temp_workspace, "secret.py"), "w", encoding="utf-8") as f:
        f.write(vuln_code)
    with open(os.path.join(temp_workspace, "clean.py"), "w", encoding="utf-8") as f:
        f.write(clean_code)

    scanner = BanditScanner()
    findings_vuln = await scanner.scan(temp_workspace, changed_files=["secret.py"])
    findings_clean = await scanner.scan(temp_workspace, changed_files=["clean.py"])

    assert any(f.rule_id == "B105" for f in findings_vuln)
    assert len(findings_clean) == 0


def test_bandit_parse_json(temp_workspace):
    """Verifies Bandit JSON output parser against official Bandit CLI JSON schema."""
    sample_json = json.dumps({
        "results": [
            {
                "filename": os.path.join(temp_workspace, "api.py"),
                "test_id": "B608",
                "test_name": "hardcoded_sql_expressions",
                "issue_severity": "HIGH",
                "issue_confidence": "HIGH",
                "issue_text": "Possible SQL injection vector through string-based query construction.",
                "line_number": 42,
                "line_range": [42],
                "code": "42 db.execute('SELECT * FROM ' + table)",
            }
        ]
    })
    scanner = BanditScanner()
    results = scanner._parse_bandit_json(sample_json, temp_workspace)

    assert len(results) == 1
    assert results[0].rule_id == "B608"
    assert results[0].severity == ScannerSeverity.CRITICAL
    assert results[0].file_path == "api.py"
    assert results[0].line_start == 42


# ==============================================================================
# 2. GITLEAKS SCANNER TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_gitleaks_detect_aws_and_github_pat(temp_workspace):
    """Verifies detection of AWS keys and GitHub Personal Access Tokens with masking."""
    dummy_aws = "AKIA" + "IOSFODNN7EXAMPLE"
    dummy_pat = "ghp_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
    content = (
        "# AWS Config\n"
        f"AWS_KEY = '{dummy_aws}'\n"
        f"GITHUB_TOKEN = '{dummy_pat}'\n"
    )
    with open(os.path.join(temp_workspace, "credentials.env"), "w", encoding="utf-8") as f:
        f.write(content)

    scanner = GitleaksScanner()
    findings = await scanner.scan(temp_workspace, changed_files=["credentials.env"])

    assert len(findings) >= 2
    aws_finding = next((f for f in findings if f.rule_id == "aws-access-token"), None)
    gh_finding = next((f for f in findings if f.rule_id == "github-pat"), None)

    assert aws_finding is not None
    assert gh_finding is not None
    assert aws_finding.severity == ScannerSeverity.CRITICAL
    # Verify secret is masked in snippet and not exposed verbatim
    assert dummy_aws not in aws_finding.code_snippet
    assert "***" in aws_finding.code_snippet


@pytest.mark.asyncio
async def test_gitleaks_detect_private_key_and_db_url(temp_workspace):
    """Verifies detection of private keys and DB connection strings."""
    content = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Y123...\n"
        "-----END RSA PRIVATE KEY-----\n"
        "DATABASE_URL = 'postgresql://admin:supersecretpassword@db.example.com:5432/prod'\n"
    )
    with open(os.path.join(temp_workspace, "config.py"), "w", encoding="utf-8") as f:
        f.write(content)

    scanner = GitleaksScanner()
    findings = await scanner.scan(temp_workspace)

    rule_ids = {f.rule_id for f in findings}
    assert "private-key" in rule_ids
    assert "db-connection-secret" in rule_ids


def test_calculate_shannon_entropy():
    """Verifies Shannon entropy calculation on random vs repetitive strings."""
    high_entropy = "h48xK9!mQ7$vL2@pZ"
    low_entropy = "aaaaaaaaaaaaaaaa"

    assert calculate_shannon_entropy(high_entropy) > 3.0
    assert calculate_shannon_entropy(low_entropy) == 0.0
    assert calculate_shannon_entropy("") == 0.0


def test_mask_secret():
    """Verifies secret masking protects credential values."""
    secret = "ghp_1234567890abcdef"
    masked = mask_secret(secret)
    assert masked.startswith("ghp")
    assert masked.endswith("def")
    assert "1234567890" not in masked
    assert mask_secret("short") == "***REDACTED***"


# ==============================================================================
# 3. ESLINT SCANNER TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_eslint_detect_eval_and_document_write(temp_workspace):
    """Verifies ESLint detection of eval(), document.write, and innerHTML."""
    content = (
        "function runDynamic(userInput) {\n"
        "    eval(userInput);\n"
        "    document.write('<div>' + userInput + '</div>');\n"
        "    document.getElementById('content').innerHTML = userInput;\n"
        "}\n"
    )
    with open(os.path.join(temp_workspace, "vuln.js"), "w", encoding="utf-8") as f:
        f.write(content)

    scanner = ESLintScanner()
    findings = await scanner.scan(temp_workspace, changed_files=["vuln.js"])

    assert len(findings) >= 3
    rule_ids = {f.rule_id for f in findings}
    assert "security/detect-eval-with-expression" in rule_ids
    assert "security/detect-document-write" in rule_ids
    assert "security/detect-innerhtml-assignment" in rule_ids


@pytest.mark.asyncio
async def test_eslint_detect_console_log_and_insecure_storage(temp_workspace):
    """Verifies quality console.log and sensitive localStorage detection."""
    content = (
        "function handleLogin(token) {\n"
        "    console.log('User logged in with token:', token);\n"
        "    localStorage.setItem('auth_token', token);\n"
        "}\n"
    )
    with open(os.path.join(temp_workspace, "auth.ts"), "w", encoding="utf-8") as f:
        f.write(content)

    scanner = ESLintScanner()
    findings = await scanner.scan(temp_workspace)

    rule_ids = {f.rule_id for f in findings}
    assert "quality/no-console-log" in rule_ids
    assert "security/detect-insecure-storage" in rule_ids


def test_eslint_parse_json(temp_workspace):
    """Verifies ESLint JSON output parser."""
    sample_json = json.dumps([
        {
            "filePath": os.path.join(temp_workspace, "src", "app.tsx"),
            "messages": [
                {
                    "ruleId": "security/detect-eval-with-expression",
                    "severity": 2,
                    "message": "eval can be harmful.",
                    "line": 15,
                    "endLine": 15,
                }
            ],
        }
    ])
    scanner = ESLintScanner()
    results = scanner._parse_eslint_json(sample_json, temp_workspace)

    assert len(results) == 1
    assert results[0].rule_id == "security/detect-eval-with-expression"
    assert results[0].severity == ScannerSeverity.HIGH
    assert results[0].line_start == 15


# ==============================================================================
# 4. SEMGREP SCANNER TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_semgrep_detect_cors_and_command_injection(temp_workspace):
    """Verifies Semgrep polyglot detection of wildcard CORS and command injection."""
    py_content = "import os\nos.system('ping ' + ip_addr)\n"
    js_content = "res.setHeader('Access-Control-Allow-Origin', '*');\n"

    with open(os.path.join(temp_workspace, "server.py"), "w", encoding="utf-8") as f:
        f.write(py_content)
    with open(os.path.join(temp_workspace, "cors.js"), "w", encoding="utf-8") as f:
        f.write(js_content)

    scanner = SemgrepScanner()
    findings = await scanner.scan(temp_workspace)

    rule_ids = {f.rule_id for f in findings}
    assert "semgrep.python.command-injection" in rule_ids
    assert "semgrep.generic.cors.wildcard" in rule_ids


@pytest.mark.asyncio
async def test_semgrep_detect_insecure_tls(temp_workspace):
    """Verifies Semgrep detection of disabled SSL/TLS certificate verification."""
    py_content = "import requests\nresponse = requests.get('https://example.com', verify=False)\n"
    with open(os.path.join(temp_workspace, "client.py"), "w", encoding="utf-8") as f:
        f.write(py_content)

    scanner = SemgrepScanner()
    findings = await scanner.scan(temp_workspace, changed_files=["client.py"])

    assert any(f.rule_id == "semgrep.python.tls.disabled-verification" for f in findings)


# ==============================================================================
# 5. BASE SCANNER SECURITY & PATH TRAVERSAL TESTS
# ==============================================================================


def test_base_scanner_path_traversal_defense(temp_workspace):
    """Verifies that path traversal attempts are detected and rejected."""
    scanner = BanditScanner()

    # Invalid workspace directory
    with pytest.raises(ValueError, match="does not exist or is not a directory"):
        scanner._validate_workspace_path(os.path.join(temp_workspace, "nonexistent"))

    # Relative path escaping root
    with pytest.raises(ValueError, match="Path traversal detected"):
        scanner._validate_relative_file_path(temp_workspace, "../../../etc/passwd")

    with pytest.raises(ValueError, match="Path traversal detected"):
        scanner._validate_relative_file_path(temp_workspace, "..\\..\\windows\\system32")


@pytest.mark.asyncio
async def test_base_scanner_timeout_handling(temp_workspace):
    """Verifies that timeouts in subprocesses are cleanly caught as ScannerTimeoutError."""
    scanner = BanditScanner(timeout_seconds=1)

    # Mock long-running command using python -c "import time; time.sleep(5)"
    with pytest.raises(ScannerTimeoutError):
        await scanner._run_subprocess(
            ["python", "-c", "import time; time.sleep(5)"],
            cwd=temp_workspace,
            timeout=1,
        )


# ==============================================================================
# 6. SCANNER ENGINE ORCHESTRATION TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_scanner_engine_parallel_execution(temp_workspace):
    """Verifies ScannerEngine runs all registered scanners concurrently and aggregates results."""
    # Write Python file with SQL injection and hardcoded secret
    py_code = (
        "password = 'supersecretpass'\n"
        "def query(uid):\n"
        "    cursor.execute(f'SELECT * FROM tbl WHERE id={uid}')\n"
    )
    with open(os.path.join(temp_workspace, "app.py"), "w", encoding="utf-8") as f:
        f.write(py_code)

    # Write JS file with eval
    js_code = "eval('alert(1)');\n"
    with open(os.path.join(temp_workspace, "index.js"), "w", encoding="utf-8") as f:
        f.write(js_code)

    engine = ScannerEngine()
    findings, summaries = await engine.scan_repository(temp_workspace)

    assert len(findings) >= 3
    assert len(summaries) == 4  # bandit, semgrep, gitleaks, eslint

    # All scanners should have completed with SUCCESS status
    for s in summaries:
        assert s.status == "SUCCESS"
        assert s.duration_ms >= 0

    scanners_found = {f.scanner for f in findings}
    assert "bandit" in scanners_found
    assert "eslint" in scanners_found


@pytest.mark.asyncio
async def test_scanner_engine_partial_failure_isolation(temp_workspace):
    """Verifies that when one scanner fails, other scanners proceed and complete normally."""
    class FailingScanner(BaseScanner):
        def __init__(self):
            super().__init__(name="failing_scanner")

        def is_available(self) -> bool:
            return True

        async def scan(self, repo_path: str, changed_files=None) -> List[NormalizedScanResult]:
            raise RuntimeError("Underlying tool segfaulted")

    py_code = "def add(a, b):\n    return a + b\n"
    with open(os.path.join(temp_workspace, "clean.py"), "w", encoding="utf-8") as f:
        f.write(py_code)

    engine = ScannerEngine([BanditScanner(), FailingScanner()])
    findings, summaries = await engine.scan_repository(temp_workspace)

    bandit_summary = next(s for s in summaries if s.scanner == "bandit")
    failing_summary = next(s for s in summaries if s.scanner == "failing_scanner")

    assert bandit_summary.status == "SUCCESS"
    assert failing_summary.status == "FAILED"
    assert "segfaulted" in failing_summary.error_message


def test_scanner_engine_filtering_utilities():
    """Verifies severity, category, and file grouping utility functions."""
    f1 = NormalizedScanResult(
        scanner="bandit",
        rule_id="B608",
        category=ScannerCategory.SECURITY,
        severity=ScannerSeverity.CRITICAL,
        file_path="db.py",
        line_start=10,
        title="SQLi",
        message="SQL Injection",
    )
    f2 = NormalizedScanResult(
        scanner="eslint",
        rule_id="quality/no-console",
        category=ScannerCategory.QUALITY,
        severity=ScannerSeverity.INFO,
        file_path="ui.js",
        line_start=5,
        title="Console",
        message="console.log",
    )

    findings = [f1, f2]

    # Filter by severity
    critical_only = ScannerEngine.filter_by_severity(findings, ScannerSeverity.CRITICAL)
    assert len(critical_only) == 1
    assert critical_only[0].rule_id == "B608"

    # Filter by category
    quality_only = ScannerEngine.filter_by_category(findings, ScannerCategory.QUALITY)
    assert len(quality_only) == 1
    assert quality_only[0].rule_id == "quality/no-console"

    # Group by file
    grouped = ScannerEngine.group_by_file(findings)
    assert "db.py" in grouped
    assert "ui.js" in grouped
