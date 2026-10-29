import pytest
import base64
from unittest.mock import AsyncMock, MagicMock
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database.session import get_db
from app.github.client import GitHubClient
from app.main import app
from app.models.base import Base
from app.models.finding import Finding
from app.models.pull_request import PullRequest
from app.models.remediation import FixPR, RemediationAttempt
from app.models.repository import Repository
from app.models.review import ReviewJob, ReviewRun
from app.models.user import User
from app.remediation.fix_pr import FixPRService
from app.schemas.remediation import FixPRCreateRequest, FixPRResponse, RemediationStatus


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
async def seeded_remediation_attempt(test_db_session: AsyncSession) -> RemediationAttempt:
    user = User(username="lead-sec", email="lead@example.com", github_id="gh_888", role="DEVELOPER")
    test_db_session.add(user)
    await test_db_session.flush()

    repo = Repository(
        github_repo_id=998877,
        name="auth-service",
        owner="codeguardian-corp",
        url="https://github.com/codeguardian-corp/auth-service",
        default_branch="main",
        language="python",
        is_active=True,
    )
    test_db_session.add(repo)
    await test_db_session.flush()

    pr = PullRequest(
        github_pr_id=112244,
        repository_id=repo.id,
        number=55,
        title="feat: JWT authentication handler",
        author="lead-sec",
        source_branch="feat/jwt-auth",
        target_branch="main",
        commit_sha="c3d4e5f67890abcdef1234567890abcdef123456",
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
        risk_score=80.0,
        risk_grade="D",
        summary="Review completed with hardcoded secret.",
        duration_ms=400,
    )
    test_db_session.add(run)
    await test_db_session.flush()

    finding = Finding(
        review_run_id=run.id,
        title="Hardcoded JWT Secret Token",
        description="Plaintext JWT secret key hardcoded in configuration.",
        severity="HIGH",
        category="SECURITY",
        confidence=1.0,
        status="OPEN",
        file_path="app/config/auth.py",
        line_start=5,
        line_end=5,
        impact="Token forgery risk.",
        recommendation="Use environment variables.",
        policy_reference="SEC-CRED-01",
        fingerprint="fp-jwt-secret-01",
    )
    test_db_session.add(finding)
    await test_db_session.flush()

    patch_str = (
        "--- a/app/config/auth.py\n"
        "+++ b/app/config/auth.py\n"
        "@@ -4,3 +4,4 @@\n"
        "+import os\n"
        "-JWT_SECRET = 'secret123'\n"
        "+JWT_SECRET = os.environ.get('JWT_SECRET', '')\n"
    )

    attempt = RemediationAttempt(
        finding_id=finding.id,
        requested_by=user.id,
        patch=patch_str,
        status=RemediationStatus.VALIDATED.value,
        validation_result={
            "overall": "PASSED",
            "patch_application": {"status": "PASSED"},
            "syntax_check": {"status": "PASSED"},
            "scanner_check": {"status": "PASSED"},
            "unit_tests": {"status": "SKIPPED"},
            "regression_check": {"status": "PASSED"},
        },
    )
    test_db_session.add(attempt)
    await test_db_session.commit()
    await test_db_session.refresh(attempt)
    return attempt


# 1. Format Fix PR Body Tests
def test_format_fix_pr_body():
    f = Finding(
        title="SQL Injection in Order Query",
        description="Dynamic string formatting allows arbitrary queries.",
        severity="CRITICAL",
        category="SECURITY",
        file_path="app/orders.py",
        line_start=14,
        policy_reference="SEC-SQL-01",
    )
    val = {
        "patch_application": {"status": "PASSED"},
        "syntax_check": {"status": "PASSED"},
        "scanner_check": {"status": "PASSED"},
        "unit_tests": {"status": "PASSED"},
        "regression_check": {"status": "PASSED"},
    }
    body = FixPRService.format_fix_pr_body(f, val)
    assert "CodeGuardian AI — Automated Fix Pull Request" in body
    assert "SQL Injection in Order Query" in body
    assert "app/orders.py:14" in body
    assert "SEC-SQL-01" in body
    assert "5-Stage Sandboxed Validation Pipeline" in body
    assert "Human developer review and approval required before merging." in body


# 2. Mock Token Fallback Tests
@pytest.mark.asyncio
async def test_create_fix_pr_mock_fallback(
    test_db_session: AsyncSession, seeded_remediation_attempt: RemediationAttempt
):
    client = GitHubClient(token="mock_token_xyz")
    service = FixPRService(client=client)

    req = FixPRCreateRequest(remediation_attempt_id=seeded_remediation_attempt.id)
    resp = await service.create_fix_pull_request(test_db_session, req)

    assert isinstance(resp, FixPRResponse)
    assert resp.status == "OPEN"
    assert resp.remediation_attempt_id == seeded_remediation_attempt.id
    assert resp.repo_name == "codeguardian-corp/auth-service"
    assert "pull/105" in resp.url
    assert "codeguardian/fix-" in resp.branch_name

    # Verify RemediationAttempt status transitioned to APPLIED
    await test_db_session.refresh(seeded_remediation_attempt)
    assert seeded_remediation_attempt.status == RemediationStatus.APPLIED.value


# 3. Gating Validation: Reject Unvalidated Remediation
@pytest.mark.asyncio
async def test_create_fix_pr_blocks_unvalidated_remediation(
    test_db_session: AsyncSession, seeded_remediation_attempt: RemediationAttempt
):
    # Change status to REJECTED
    seeded_remediation_attempt.status = RemediationStatus.REJECTED.value
    await test_db_session.commit()

    service = FixPRService(client=GitHubClient(token="mock_token"))
    req = FixPRCreateRequest(remediation_attempt_id=seeded_remediation_attempt.id)

    with pytest.raises(ValueError, match="Only 'VALIDATED' patches can be submitted"):
        await service.create_fix_pull_request(test_db_session, req)


# 4. Gating Validation: Reject Duplicate Fix PR
@pytest.mark.asyncio
async def test_create_fix_pr_blocks_duplicate(
    test_db_session: AsyncSession, seeded_remediation_attempt: RemediationAttempt
):
    service = FixPRService(client=GitHubClient(token="mock_token"))
    req = FixPRCreateRequest(remediation_attempt_id=seeded_remediation_attempt.id)

    # First creation succeeds
    await service.create_fix_pull_request(test_db_session, req)

    # Second creation must fail
    with pytest.raises(ValueError, match="Fix PR already exists"):
        await service.create_fix_pull_request(test_db_session, req)


# 5. Live Mocked Client Flow
@pytest.mark.asyncio
async def test_create_fix_pr_live_mocked(
    test_db_session: AsyncSession, seeded_remediation_attempt: RemediationAttempt
):
    mock_client = MagicMock(spec=GitHubClient)
    mock_client.token = "ghp_real_pat_secret_999"
    mock_client.create_branch = AsyncMock(return_value={"ref": "refs/heads/codeguardian/fix-123"})

    orig_content = "import sys\n# Auth config\nJWT_SECRET = 'secret123'\n"
    encoded = base64.b64encode(orig_content.encode("utf-8")).decode("utf-8")
    mock_client.get_file_contents = AsyncMock(return_value={"sha": "blob_sha_123", "content": encoded})
    mock_client.create_or_update_file_contents = AsyncMock(return_value={"commit": {"sha": "new_sha"}})
    mock_client.create_pull_request = AsyncMock(return_value={
        "id": 9901,
        "number": 88,
        "html_url": "https://github.com/codeguardian-corp/auth-service/pull/88",
    })

    service = FixPRService(client=mock_client)
    req = FixPRCreateRequest(remediation_attempt_id=seeded_remediation_attempt.id)
    resp = await service.create_fix_pull_request(test_db_session, req)

    assert resp.number == 88
    assert resp.github_pr_id == 9901
    assert "pull/88" in resp.url

    # Verify calls executed in sequence
    mock_client.create_branch.assert_called_once()
    mock_client.get_file_contents.assert_called_once()
    mock_client.create_or_update_file_contents.assert_called_once()
    mock_client.create_pull_request.assert_called_once()


# 6. Webhook Synchronization (Merged vs Closed)
@pytest.mark.asyncio
async def test_handle_fix_pr_webhook_events(
    test_db_session: AsyncSession, seeded_remediation_attempt: RemediationAttempt
):
    service = FixPRService(client=GitHubClient(token="mock_token"))
    req = FixPRCreateRequest(remediation_attempt_id=seeded_remediation_attempt.id)
    fix_pr_resp = await service.create_fix_pull_request(test_db_session, req)

    # A. Webhook: PR is merged
    updated_pr = await service.handle_fix_pr_webhook_event(
        session=test_db_session,
        github_pr_id=fix_pr_resp.github_pr_id,
        action="closed",
        merged=True,
    )
    assert updated_pr is not None
    assert updated_pr.status == "MERGED"

    # Finding status must automatically transition to RESOLVED
    finding = seeded_remediation_attempt.finding
    await test_db_session.refresh(finding)
    assert finding.status == "RESOLVED"

    # B. Webhook: PR closed without merge
    closed_pr = await service.handle_fix_pr_webhook_event(
        session=test_db_session,
        github_pr_id=fix_pr_resp.github_pr_id,
        action="closed",
        merged=False,
    )
    assert closed_pr.status == "CLOSED"


# 7. REST API Endpoints Verification
@pytest.mark.asyncio
async def test_fix_pr_rest_api_endpoints(
    test_db_session: AsyncSession, seeded_remediation_attempt: RemediationAttempt
):
    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # A. Create Fix PR via REST API
            post_resp = await client.post(
                f"/api/v1/remediation/{seeded_remediation_attempt.id}/fix-pr",
                json={"custom_title": "Fix: Automated JWT credential remediation"},
            )
            assert post_resp.status_code == 201
            data = post_resp.json()
            assert data["remediation_attempt_id"] == seeded_remediation_attempt.id
            assert data["status"] == "OPEN"
            fix_pr_id = data["id"]

            # B. Get Fix PR details
            get_resp = await client.get(f"/api/v1/fix-prs/{fix_pr_id}")
            assert get_resp.status_code == 200
            get_data = get_resp.json()
            assert get_data["id"] == fix_pr_id
            assert get_data["number"] == data["number"]

            # C. 400 Bad Request on duplicate creation
            dup_resp = await client.post(
                f"/api/v1/remediation/{seeded_remediation_attempt.id}/fix-pr"
            )
            assert dup_resp.status_code == 400

            # D. 404 Not Found on invalid Fix PR ID
            not_found_resp = await client.get("/api/v1/fix-prs/non-existent-uuid")
            assert not_found_resp.status_code == 404

    finally:
        app.dependency_overrides.clear()
