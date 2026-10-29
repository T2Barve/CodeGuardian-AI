import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database.session import get_db
from app.main import app
from app.models.base import Base
from app.models.finding import Finding
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob, ReviewRun
from app.models.user import User
from app.remediation.generator import PatchGenerator
from app.remediation.sandbox import SandboxPipeline
from app.remediation.service import RemediationService
from app.schemas.remediation import (
    RemediationCandidate,
    RemediationResponse,
    RemediationStatus,
    ValidationStageStatus,
)


@pytest.fixture
async def test_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def seeded_finding(test_db_session: AsyncSession) -> Finding:
    user = User(username="sec-dev", email="sec@example.com", github_id="gh_777", role="DEVELOPER")
    test_db_session.add(user)
    await test_db_session.flush()

    repo = Repository(
        github_repo_id=556677,
        name="billing-service",
        owner="codeguardian-corp",
        url="https://github.com/codeguardian-corp/billing-service",
        default_branch="main",
        language="python",
        is_active=True,
    )
    test_db_session.add(repo)
    await test_db_session.flush()

    pr = PullRequest(
        github_pr_id=889900,
        repository_id=repo.id,
        number=202,
        title="fix: database user lookup",
        author="sec-dev",
        source_branch="fix/user-lookup",
        target_branch="main",
        commit_sha="b8c9d0e1f234567890abcdef1234567890abcdef",
        status="OPEN",
    )
    test_db_session.add(pr)
    await test_db_session.flush()

    job = ReviewJob(pull_request_id=pr.id, status="COMPLETED")
    test_db_session.add(job)
    await test_db_session.flush()

    run = ReviewRun(
        review_job_id=job.id,
        status="SUCCESS",
        risk_score=75.0,
        risk_grade="D",
        summary="Review completed with critical finding.",
        duration_ms=500,
    )
    test_db_session.add(run)
    await test_db_session.flush()

    finding = Finding(
        review_run_id=run.id,
        title="SQL Injection via Formatted String",
        description="User query is interpolated directly into raw SQL string.",
        severity="CRITICAL",
        category="SECURITY",
        confidence=0.95,
        status="OPEN",
        file_path="app/db/users.py",
        line_start=3,
        line_end=4,
        impact="Full unauthorized database read/write access.",
        recommendation="Use parameterized query syntax.",
        policy_reference="SEC-SQL-01",
        fingerprint="fp-sql-billing-01",
    )
    test_db_session.add(finding)
    await test_db_session.commit()
    await test_db_session.refresh(finding)
    return finding


# 1. Patch Generator Tests
def test_patch_generator_unified_diff_creation():
    orig = "def get_user(id):\n    return db.query(id)\n"
    fixed = "def get_user(id):\n    # Parameterized query\n    return db.query_safe(id)\n"
    diff = PatchGenerator.create_unified_diff(orig, fixed, "app/db.py")

    assert "--- a/app/db.py" in diff
    assert "+++ b/app/db.py" in diff
    assert "+    # Parameterized query" in diff
    assert "-    return db.query(id)" in diff


def test_patch_generator_deterministic_fallbacks():
    gen = PatchGenerator()

    # A. SQL Injection Fallback
    f_sql = Finding(
        file_path="app/api.py",
        title="SQL Injection in Payments",
        description="cursor.execute with f-string",
        severity="CRITICAL",
        category="SECURITY",
        line_start=2,
    )
    orig_sql = "def find(id):\n    cursor.execute(f'SELECT * FROM payments WHERE id = {id}')\n"
    cand_sql = gen._generate_deterministic_fallback_patch(f_sql, orig_sql)
    assert cand_sql.target_file == "app/api.py"
    assert "--- a/app/api.py" in cand_sql.patch
    assert "%s" in cand_sql.patch or "parameter" in cand_sql.patch.lower()

    # B. Hardcoded Secret Fallback
    f_sec = Finding(
        file_path="app/keys.py",
        title="Hardcoded API Secret Key",
        description="Stripe key committed in plaintext",
        severity="HIGH",
        category="SECURITY",
        line_start=1,
    )
    orig_sec = "STRIPE_SECRET = '" + "sk_live_" + "1234567890abcdef'\n"
    cand_sec = gen._generate_deterministic_fallback_patch(f_sec, orig_sec)
    assert "os.environ.get" in cand_sec.patch

    # C. Permissive CORS Fallback
    f_cors = Finding(
        file_path="app/server.py",
        title="Permissive CORS Wildcard",
        description="Access-Control-Allow-Origin: *",
        severity="MEDIUM",
        category="SECURITY",
    )
    orig_cors = "headers = {'Access-Control-Allow-Origin': '*'}\n"
    cand_cors = gen._generate_deterministic_fallback_patch(f_cors, orig_cors)
    assert "ALLOWED_ORIGIN" in cand_cors.patch or "os.environ" in cand_cors.patch

    # D. Deprecated MD5 Fallback
    f_md5 = Finding(
        file_path="app/hash.py",
        title="Weak Cryptographic Hash (MD5)",
        description="Insecure hashlib.md5 used",
        severity="LOW",
        category="SECURITY",
    )
    orig_md5 = "import hashlib\ndef sign(data):\n    return hashlib.md5(data).hexdigest()\n"
    cand_md5 = gen._generate_deterministic_fallback_patch(f_md5, orig_md5)
    assert "hashlib.sha256" in cand_md5.patch

    # E. Unsafe YAML Fallback
    f_yaml = Finding(
        file_path="app/config.py",
        title="Unsafe YAML Load",
        description="yaml.load without safe loader",
        severity="HIGH",
        category="SECURITY",
    )
    orig_yaml = "import yaml\nconfig = yaml.load(data)\n"
    cand_yaml = gen._generate_deterministic_fallback_patch(f_yaml, orig_yaml)
    assert "yaml.safe_load" in cand_yaml.patch


# 2. Pure Python Unified Diff Application Tests
def test_sandbox_pure_python_diff_application():
    orig = "line 1\nline 2\nline 3\n"
    fixed = "line 1\nline 2 updated\nline 3\n"
    diff = PatchGenerator.create_unified_diff(orig, fixed, "test.txt")

    success, patched, err = SandboxPipeline.apply_unified_diff_to_string(orig, diff)
    assert success is True
    assert patched == fixed
    assert err == ""

    # Test corrupted patch
    success_bad, _, err_bad = SandboxPipeline.apply_unified_diff_to_string(orig, "invalid garbage patch")
    assert success_bad is False
    assert "Malformed" in err_bad or "missing" in err_bad


# 3. Sandbox Syntax Validation Tests
def test_sandbox_syntax_validation():
    sandbox = SandboxPipeline()

    # A. Valid Python
    valid_py = "def calculate(a, b):\n    return a + b\n"
    res_val = sandbox.validate_syntax(valid_py, "app/calc.py")
    assert res_val.status == ValidationStageStatus.PASSED
    assert "AST parsed cleanly" in res_val.message

    # B. Invalid Python (SyntaxError)
    invalid_py = "def calculate(a, b\n    return a + b\n"
    res_inval = sandbox.validate_syntax(invalid_py, "app/calc.py")
    assert res_inval.status == ValidationStageStatus.FAILED
    assert "Syntax error" in res_inval.message

    # C. Valid JSON
    valid_json = '{"name": "codeguardian", "active": true}'
    res_json = sandbox.validate_syntax(valid_json, "config.json")
    assert res_json.status == ValidationStageStatus.PASSED

    # D. Invalid JSON
    invalid_json = '{"name": "codeguardian", active: true'
    res_json_err = sandbox.validate_syntax(invalid_json, "config.json")
    assert res_json_err.status == ValidationStageStatus.FAILED


# 4. Sandbox Scanner & Regression Checks
@pytest.mark.asyncio
async def test_sandbox_scanner_and_regression_checks(tmp_path):
    sandbox = SandboxPipeline()

    # Scanner check test
    test_file = tmp_path / "test_api.py"
    test_file.write_text("import os\nSTRIPE_SECRET = os.environ.get('STRIPE_SECRET', '')\n", encoding="utf-8")

    f_secret = Finding(
        file_path="test_api.py",
        title="Hardcoded API Secret Key",
        severity="HIGH",
        category="SECURITY",
    )
    res_scan = await sandbox.validate_scanner(tmp_path, "test_api.py", f_secret)
    assert res_scan.status == ValidationStageStatus.PASSED
    assert "Target vulnerability eliminated" in res_scan.message

    # Regression check: normal non-destructive change
    orig = "import os\nimport sys\ndef run():\n    return 42\n"
    patched = "import os\nimport sys\ndef run():\n    # Guard\n    return 42\n"
    res_reg = sandbox.validate_regression(orig, patched)
    assert res_reg.status == ValidationStageStatus.PASSED

    # Regression check: catastrophic truncation
    catastrophic = "import os\n"
    res_reg_fail = sandbox.validate_regression(orig * 5, catastrophic)
    assert res_reg_fail.status == ValidationStageStatus.FAILED
    assert "truncated" in res_reg_fail.message


# 5. Full 5-Stage Sandboxed Pipeline
@pytest.mark.asyncio
async def test_sandbox_5_stage_pipeline_full_success():
    sandbox = SandboxPipeline()
    orig = (
        "import os\n"
        "def query_db(uid):\n"
        "    cursor.execute(f'SELECT * FROM payments WHERE id = {uid}')\n"
    )
    fixed = (
        "import os\n"
        "def query_db(uid):\n"
        "    cursor.execute('SELECT * FROM payments WHERE id = %s', (uid,))\n"
    )
    diff = PatchGenerator.create_unified_diff(orig, fixed, "app/db.py")

    finding = Finding(
        file_path="app/db.py",
        title="SQL Injection",
        severity="CRITICAL",
        category="SECURITY",
        line_start=3,
    )

    result = await sandbox.execute_validation_pipeline(
        original_content=orig,
        patch_str=diff,
        finding=finding,
    )

    assert result.overall == ValidationStageStatus.PASSED
    assert result.can_create_pr is True
    assert result.patch_application.status == ValidationStageStatus.PASSED
    assert result.syntax_check.status == ValidationStageStatus.PASSED
    assert result.scanner_check.status == ValidationStageStatus.PASSED
    assert result.unit_tests.status == ValidationStageStatus.SKIPPED  # No tests in sandbox
    assert result.regression_check.status == ValidationStageStatus.PASSED


@pytest.mark.asyncio
async def test_sandbox_pipeline_syntax_failure():
    sandbox = SandboxPipeline()
    orig = "def add(a, b):\n    return a + b\n"
    # Broken patch that causes SyntaxError
    broken_fixed = "def add(a, b:\n    return a + b\n"
    diff = PatchGenerator.create_unified_diff(orig, broken_fixed, "app/math.py")

    finding = Finding(file_path="app/math.py", title="Quality Smells", severity="LOW", category="QUALITY")
    result = await sandbox.execute_validation_pipeline(orig, diff, finding)

    assert result.overall == ValidationStageStatus.FAILED
    assert result.can_create_pr is False
    assert result.syntax_check.status == ValidationStageStatus.FAILED
    assert "Syntax error" in (result.error_summary or "")


# 6. Remediation Service End-to-End Orchestration
@pytest.mark.asyncio
async def test_remediation_service_generate_and_validate(
    test_db_session: AsyncSession, seeded_finding: Finding
):
    service = RemediationService()

    resp = await service.generate_and_validate_remediation(
        session=test_db_session,
        finding_id=seeded_finding.id,
        custom_instructions="Ensure parameterized queries are used.",
    )

    assert isinstance(resp, RemediationResponse)
    assert resp.finding_id == seeded_finding.id
    assert resp.status == RemediationStatus.VALIDATED
    assert resp.can_create_pr is True
    assert "--- a/app/db/users.py" in resp.patch
    assert resp.validation_result is not None
    assert resp.validation_result["overall"] == "PASSED"

    # Test retrieval
    retrieved = await service.get_remediation(test_db_session, resp.id)
    assert retrieved is not None
    assert retrieved.id == resp.id
    assert retrieved.status == RemediationStatus.VALIDATED

    # Test list for finding
    listed = await service.list_remediations_for_finding(test_db_session, seeded_finding.id)
    assert listed.total == 1
    assert listed.items[0].id == resp.id


# 7. REST API Endpoints Verification
@pytest.mark.asyncio
async def test_remediation_api_endpoints(
    test_db_session: AsyncSession, seeded_finding: Finding
):
    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # A. Trigger Remediation
            post_resp = await client.post(
                f"/api/v1/findings/{seeded_finding.id}/remediate",
                json={"custom_instructions": "Use SQLAlchemy parameterized parameters"},
            )
            assert post_resp.status_code == 201
            data = post_resp.json()
            assert data["finding_id"] == seeded_finding.id
            assert data["status"] == "VALIDATED"
            assert data["can_create_pr"] is True
            remediation_id = data["id"]

            # B. Get Remediation Details
            get_resp = await client.get(f"/api/v1/remediation/{remediation_id}")
            assert get_resp.status_code == 200
            get_data = get_resp.json()
            assert get_data["id"] == remediation_id
            assert get_data["can_create_pr"] is True

            # C. List Remediations for Finding
            list_resp = await client.get(f"/api/v1/findings/{seeded_finding.id}/remediations")
            assert list_resp.status_code == 200
            list_data = list_resp.json()
            assert list_data["total"] >= 1
            assert list_data["items"][0]["id"] == remediation_id

            # D. Revalidate Remediation
            val_resp = await client.post(f"/api/v1/remediation/{remediation_id}/validate")
            assert val_resp.status_code == 200
            assert val_resp.json()["status"] == "VALIDATED"

            # E. 404 on Invalid Finding
            bad_finding = await client.post("/api/v1/findings/non-existent-uuid/remediate")
            assert bad_finding.status_code == 404

            # F. 404 on Invalid Remediation ID
            bad_remed = await client.get("/api/v1/remediation/non-existent-uuid")
            assert bad_remed.status_code == 404

    finally:
        app.dependency_overrides.clear()
