import os
import tempfile
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
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
from app.main import app
from app.models.finding import Finding
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob, ReviewRun
from app.repositories.pull_request_repository import PullRequestRepository
from app.repositories.repository_repository import RepositoryRepository
from app.repositories.review_repository import ReviewJobRepository, ReviewRunRepository
from app.schemas.queue import ReviewJobPayload
from app.schemas.scanner import (
    NormalizedScanResult,
    ScannerCategory,
    ScannerSeverity,
)
from app.workers.queue import MemoryReviewQueue
from app.workers.review_worker import ReviewWorker


# ==============================================================================
# 1. FINGERPRINTING & CANONICAL CLASSIFICATION TESTS
# ==============================================================================


def test_normalize_file_path():
    """Verifies that paths with mixed separators and prefixes normalize consistently."""
    assert normalize_file_path("src\\utils\\crypto.py") == "src/utils/crypto.py"
    assert normalize_file_path("./src/utils/crypto.py") == "src/utils/crypto.py"
    assert normalize_file_path("/src/utils/crypto.py") == "src/utils/crypto.py"
    assert normalize_file_path("SRC/UTILS/CRYPTO.PY") == "src/utils/crypto.py"


def test_canonical_issue_type_mapping():
    """Verifies mapping of heterogeneous tool rules to standardized issue classes."""
    assert get_canonical_issue_type("B608") == "cwe-89-sqli"
    assert get_canonical_issue_type("semgrep.python.sqli.format") == "cwe-89-sqli"
    assert get_canonical_issue_type("B602") == "cwe-78-cmdi"
    assert get_canonical_issue_type("aws-access-token") == "cwe-798-hardcoded-secret"
    assert get_canonical_issue_type("security/detect-document-write") == "cwe-79-xss"
    assert get_canonical_issue_type("unknown-custom-rule") == "unknown-custom-rule"


def test_deterministic_finding_fingerprint():
    """Verifies that fingerprint generation is strictly deterministic and cross-tool consistent."""
    fp1 = generate_finding_fingerprint(
        file_path="services/auth.py",
        line_start=42,
        category="SECURITY",
        rule_id="B608",
    )
    fp2 = generate_finding_fingerprint(
        file_path="services\\auth.py",
        line_start=42,
        category="SECURITY",
        rule_id="B608",
    )
    # Cross-tool equivalent rule should produce identical fingerprint
    fp_semgrep = generate_finding_fingerprint(
        file_path="services/auth.py",
        line_start=42,
        category="SECURITY",
        rule_id="semgrep.python.sqli.format",
    )

    assert fp1 == fp2
    assert fp1 == fp_semgrep
    assert len(fp1) == 64  # SHA-256 hex string

    # Different line must produce different fingerprint
    fp_diff_line = generate_finding_fingerprint(
        file_path="services/auth.py",
        line_start=43,
        category="SECURITY",
        rule_id="B608",
    )
    assert fp1 != fp_diff_line


# ==============================================================================
# 2. CORRELATION & EVIDENCE MERGING TESTS
# ==============================================================================


def test_resolve_highest_severity():
    """Verifies that the highest severity is correctly selected."""
    assert resolve_highest_severity(["LOW", "CRITICAL", "MEDIUM"]) == "CRITICAL"
    assert resolve_highest_severity(["LOW", "MEDIUM"]) == "MEDIUM"
    assert resolve_highest_severity(["HIGH", "HIGH"]) == "HIGH"
    assert resolve_highest_severity(["INFO"]) == "INFO"


def test_combine_confidence():
    """Verifies that multiple corroborating tools boost detection confidence."""
    single_tool_conf = combine_confidence([0.90], distinct_tools_count=1)
    multi_tool_conf = combine_confidence([0.90, 0.95], distinct_tools_count=2)

    assert single_tool_conf == 0.90
    assert multi_tool_conf > single_tool_conf
    assert multi_tool_conf <= 1.0


def test_correlate_findings_merging():
    """Verifies that multiple tools reporting the same flaw on the same line are merged."""
    finding_bandit = NormalizedScanResult(
        scanner="bandit",
        rule_id="B608",
        category=ScannerCategory.SECURITY,
        severity=ScannerSeverity.HIGH,
        confidence=0.92,
        file_path="views/user.py",
        line_start=15,
        line_end=15,
        title="Bandit SQLi",
        message="SQL string formatting detected.",
        code_snippet="db.execute(f'SELECT * FROM u WHERE id={uid}')",
    )
    finding_semgrep = NormalizedScanResult(
        scanner="semgrep",
        rule_id="semgrep.python.sqli.format",
        category=ScannerCategory.SECURITY,
        severity=ScannerSeverity.CRITICAL,
        confidence=0.95,
        file_path="views/user.py",
        line_start=15,
        line_end=16,
        title="Semgrep SQLi",
        message="Raw SQL formatted dynamically.",
        code_snippet="db.execute(f'SELECT * FROM u WHERE id={uid}')",
    )

    correlated = correlate_findings([finding_bandit, finding_semgrep], line_tolerance=2)

    assert len(correlated) == 1
    c = correlated[0]
    # Severity should escalate to CRITICAL
    assert c.severity == "CRITICAL"
    # Both tools involved
    assert set(c.tools_involved) == {"bandit", "semgrep"}
    # Contains 2 distinct evidence items
    assert len(c.evidence_items) == 2
    # Combined confidence should be boosted
    assert c.confidence > 0.95
    # Enriched policy and remediation details
    assert "CWE-89" in c.policy_reference or "SEC-POL-04" in c.policy_reference
    assert "parameterized queries" in c.recommendation.lower()


def test_correlate_findings_line_tolerance():
    """Verifies that adjacent lines within tolerance are clustered into one finding."""
    f1 = NormalizedScanResult(
        scanner="eslint",
        rule_id="security/detect-document-write",
        category=ScannerCategory.SECURITY,
        severity=ScannerSeverity.HIGH,
        file_path="app.js",
        line_start=20,
        title="XSS 1",
        message="document.write used",
    )
    f2 = NormalizedScanResult(
        scanner="semgrep",
        rule_id="semgrep.js.dom-xss.innerhtml",
        category=ScannerCategory.SECURITY,
        severity=ScannerSeverity.HIGH,
        file_path="app.js",
        line_start=21,
        title="XSS 2",
        message="innerHTML used",
    )

    correlated = correlate_findings([f1, f2], line_tolerance=2)
    assert len(correlated) == 1
    assert correlated[0].line_start == 20
    assert correlated[0].line_end == 21
    assert len(correlated[0].evidence_items) == 2


# ==============================================================================
# 3. FINDING ENGINE TESTS
# ==============================================================================


def test_finding_engine_process_and_severity_breakdown():
    """Verifies FindingEngine processing, sorting, and severity counting."""
    engine = FindingEngine()

    f_crit = NormalizedScanResult(
        scanner="bandit",
        rule_id="B608",
        category=ScannerCategory.SECURITY,
        severity=ScannerSeverity.CRITICAL,
        file_path="a.py",
        line_start=5,
        title="Crit",
        message="crit msg",
    )
    f_med = NormalizedScanResult(
        scanner="eslint",
        rule_id="security/detect-insecure-storage",
        category=ScannerCategory.SECURITY,
        severity=ScannerSeverity.MEDIUM,
        file_path="b.js",
        line_start=10,
        title="Med",
        message="med msg",
    )

    correlated = engine.process_scan_results([f_med, f_crit])
    assert len(correlated) == 2
    # Verify deterministic sorting (CRITICAL first)
    assert correlated[0].severity == "CRITICAL"
    assert correlated[1].severity == "MEDIUM"

    breakdown = engine.get_severity_breakdown(correlated)
    assert breakdown["CRITICAL"] == 1
    assert breakdown["MEDIUM"] == 1
    assert breakdown["HIGH"] == 0


# ==============================================================================
# 4. DATABASE PERSISTENCE & SERVICE TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_finding_service_persistence_and_query(db_session: AsyncSession):
    """Verifies FindingService persists findings, evidence, and handles queries."""
    # 1. Setup repository, PR, and ReviewRun in database
    repo_repository = RepositoryRepository(db_session)
    pr_repo = PullRequestRepository(db_session)
    job_repo = ReviewJobRepository(db_session)
    run_repo = ReviewRunRepository(db_session)

    repo = await repo_repository.create(
        github_repo_id=77788899,
        name="test-repo",
        owner="test-owner",
        url="https://github.com/test-owner/test-repo",
    )
    pr = await pr_repo.create(
        github_pr_id=123456,
        repository_id=repo.id,
        number=1,
        title="Fix vulnerability",
        author="dev",
        source_branch="patch",
        target_branch="main",
        commit_sha="abcdef1234567890",
    )
    job = await job_repo.create(pull_request_id=pr.id)
    review_run = await run_repo.create(review_job_id=job.id)

    # 2. Correlate and persist findings
    raw = [
        NormalizedScanResult(
            scanner="bandit",
            rule_id="B608",
            category=ScannerCategory.SECURITY,
            severity=ScannerSeverity.CRITICAL,
            confidence=0.98,
            file_path="models/db.py",
            line_start=50,
            title="SQL Injection",
            message="SQL injection in db.py",
            code_snippet="db.execute('SELECT * ' + inp)",
        )
    ]
    correlated = FindingEngine().process_scan_results(raw)
    persisted = await FindingService.persist_findings(
        session=db_session,
        review_run_id=review_run.id,
        correlated_findings=correlated,
    )

    assert len(persisted) == 1
    finding_id = persisted[0].id

    # 3. Retrieve finding with evidence
    finding_with_ev = await FindingService.get_finding_by_id(db_session, finding_id)
    assert finding_with_ev is not None
    assert finding_with_ev.severity == "CRITICAL"
    assert len(finding_with_ev.evidence) == 1
    assert finding_with_ev.evidence[0].tool == "bandit"

    # 4. Update status with audit logging
    updated = await FindingService.update_finding_status(
        session=db_session,
        finding_id=finding_id,
        new_status="FALSE_POSITIVE",
        actor="sec-lead",
        reason="Sanitized by upstream gateway middleware",
    )
    assert updated.status == "FALSE_POSITIVE"

    # 5. Idempotent re-run guard
    re_persisted = await FindingService.persist_findings(
        session=db_session,
        review_run_id=review_run.id,
        correlated_findings=correlated,
    )
    assert len(re_persisted) == 1
    # Finding entity must NOT be duplicated
    all_findings = await FindingService.list_findings_by_review(db_session, review_run.id)
    assert len(all_findings) == 1


# ==============================================================================
# 5. FINDINGS REST API ENDPOINTS TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_findings_api_endpoints(db_session: AsyncSession):
    """Verifies GET /findings, GET /reviews/{id}/findings, and PATCH /findings/{id}/status endpoints."""
    # Seed review and finding
    repo_repository = RepositoryRepository(db_session)
    pr_repo = PullRequestRepository(db_session)
    job_repo = ReviewJobRepository(db_session)
    run_repo = ReviewRunRepository(db_session)

    repo = await repo_repository.create(
        github_repo_id=99900011,
        name="api-test-repo",
        owner="api-test-owner",
        url="https://github.com/api-test-owner/api-test-repo",
    )
    pr = await pr_repo.create(
        github_pr_id=987654,
        repository_id=repo.id,
        number=10,
        title="API Test PR",
        author="tester",
        source_branch="test",
        target_branch="main",
        commit_sha="112233445566",
    )
    job = await job_repo.create(pull_request_id=pr.id)
    review_run = await run_repo.create(review_job_id=job.id)

    raw = [
        NormalizedScanResult(
            scanner="gitleaks",
            rule_id="aws-access-token",
            category=ScannerCategory.SECRET,
            severity=ScannerSeverity.CRITICAL,
            confidence=0.99,
            file_path="config.env",
            line_start=2,
            title="AWS Key",
            message="AWS Access Key detected",
            code_snippet="AKIA***EXAMPLE",
        )
    ]
    correlated = FindingEngine().process_scan_results(raw)
    persisted = await FindingService.persist_findings(
        session=db_session,
        review_run_id=review_run.id,
        correlated_findings=correlated,
    )
    finding_id = persisted[0].id

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test 1: List findings for review
        resp = await client.get(f"/api/v1/reviews/{review_run.id}/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["severity"] == "CRITICAL"
        assert data["severity_breakdown"]["CRITICAL"] == 1

        # Test 2: Get single finding
        resp_single = await client.get(f"/api/v1/findings/{finding_id}")
        assert resp_single.status_code == 200
        single_data = resp_single.json()
        assert single_data["id"] == finding_id
        assert single_data["category"] == "SECRET"
        assert len(single_data["evidence"]) == 1

        # Test 3: Patch status
        resp_patch = await client.patch(
            f"/api/v1/findings/{finding_id}/status",
            json={"status": "RESOLVED", "reason": "Rotated AWS key"},
        )
        assert resp_patch.status_code == 200
        assert resp_patch.json()["status"] == "RESOLVED"

        # Test 4: 404 on nonexistent finding
        resp_404 = await client.get("/api/v1/findings/nonexistent-uuid")
        assert resp_404.status_code == 404

    app.dependency_overrides.clear()


# ==============================================================================
# 6. E2E WORKER SCANNING & FINDING SYNTHESIS TEST
# ==============================================================================


@pytest.mark.asyncio
async def test_worker_end_to_end_scanning_and_finding_persistence(db_session: AsyncSession):
    """
    End-to-End integration test:
    Worker processes a review job with a workspace path containing real security vulnerabilities.
    Verifies that the ReviewWorker executes the ScannerEngine, passes outputs to FindingEngine,
    and automatically persists Finding and FindingEvidence records into PostgreSQL.
    """
    repo_repository = RepositoryRepository(db_session)
    pr_repo = PullRequestRepository(db_session)
    job_repo = ReviewJobRepository(db_session)
    run_repo = ReviewRunRepository(db_session)

    with tempfile.TemporaryDirectory() as temp_repo:
        # Write real vulnerable Python code into temporary repository
        vuln_py = (
            "import os\n"
            "password = 'hardcodedsecret123'\n"
            "def handle_query(user_id):\n"
            "    cursor.execute(f'SELECT * FROM accounts WHERE id = {user_id}')\n"
        )
        with open(os.path.join(temp_repo, "handler.py"), "w", encoding="utf-8") as f:
            f.write(vuln_py)

        repo = await repo_repository.create(
            github_repo_id=88811122,
            name="vulnerable-demo-repo",
            owner="demo-corp",
            url="https://github.com/demo-corp/vulnerable-demo-repo",
        )
        pr = await pr_repo.create(
            github_pr_id=555666,
            repository_id=repo.id,
            number=42,
            title="Security demo PR",
            author="attacker",
            source_branch="exploit-test",
            target_branch="main",
            commit_sha="deadbeef123456",
        )
        job = await job_repo.create(pull_request_id=pr.id)

        # Enqueue payload with workspace_path in metadata
        payload = ReviewJobPayload(
            job_id=job.id,
            pull_request_id=pr.id,
            repo_name=repo.name,
            repo_owner=repo.owner,
            pr_number=pr.number,
            commit_sha=pr.commit_sha,
            metadata={"workspace_path": temp_repo},
        )

        queue = MemoryReviewQueue()
        await queue.enqueue_review(payload)

        # Worker processes the job
        worker = ReviewWorker(
            queue=queue,
            session_factory=lambda: db_session,
        )
        success = await worker.run_once()
        assert success is True

        # Verify job and run state
        updated_job = await job_repo.get(job.id)
        assert updated_job.status == "COMPLETED"

        run = await run_repo.get_by_job_id(job.id)
        assert run is not None
        assert run.status == "SUCCESS"
        assert "findings synthesized" in run.summary

        # Verify findings persisted in database
        findings = await FindingService.list_findings_by_review(db_session, run.id)
        assert len(findings) >= 2  # SQL injection + Hardcoded secret
        categories = {f.category for f in findings}
        assert "SECURITY" in categories or "SECRET" in categories
