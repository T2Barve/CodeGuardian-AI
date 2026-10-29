import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database.session import get_db
from app.github.client import GitHubClient
from app.github.reporter import GitHubReporter, COMMENT_MARKER_PREFIX
from app.main import app
from app.models.base import Base
from app.models.finding import Finding
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob, ReviewRun
from app.models.user import User
from app.reports.service import ReportService
from app.schemas.github import GitHubPublishResult, GitHubReportPreview
from app.schemas.report import (
    ReportFindingItem,
    ReviewReport,
    ReviewReportSummary,
)
from app.schemas.risk import CategoryRiskBreakdown, RiskGrade, RiskLevel


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
async def seeded_review_run(test_db_session: AsyncSession) -> ReviewRun:
    user = User(
        username="lead-dev",
        email="lead@example.com",
        github_id="gh_99999",
        role="DEVELOPER",
    )
    test_db_session.add(user)
    await test_db_session.flush()

    repo = Repository(
        github_repo_id=112233,
        name="secure-microservice",
        owner="codeguardian-corp",
        url="https://github.com/codeguardian-corp/secure-microservice",
        default_branch="main",
        language="python",
        is_active=True,
    )
    test_db_session.add(repo)
    await test_db_session.flush()

    pr = PullRequest(
        github_pr_id=445566,
        repository_id=repo.id,
        number=101,
        title="feat: Payment processing and auth endpoints",
        author="lead-dev",
        source_branch="feat/payment-auth",
        target_branch="main",
        commit_sha="e7a4b1c2d3e4f56789012345678901234567890a",
        status="OPEN",
    )
    test_db_session.add(pr)
    await test_db_session.flush()

    job = ReviewJob(
        pull_request_id=pr.id,
        status="RUNNING",
    )
    test_db_session.add(job)
    await test_db_session.flush()

    run = ReviewRun(
        review_job_id=job.id,
        status="SUCCESS",
        risk_score=78.5,
        risk_grade="D",
        summary="Automated review detected critical SQL injection and hardcoded API tokens.",
        duration_ms=450,
    )
    test_db_session.add(run)
    await test_db_session.flush()

    # Add findings
    f1 = Finding(
        review_run_id=run.id,
        title="SQL Injection Vulnerability",
        description="Raw string formatting in SQL query allows arbitrary SQL execution.",
        severity="CRITICAL",
        category="SECURITY",
        file_path="app/api/payments.py",
        line_start=45,
        line_end=48,
        confidence=1.0,
        status="OPEN",
        impact="Full database compromise",
        recommendation="Use parameterized query with bound parameters.",
        policy_reference="SEC-SQL-01",
        fingerprint="fp-sql-inj-001",
    )
    f2 = Finding(
        review_run_id=run.id,
        title="Hardcoded API Secret",
        description="Plaintext Stripe secret key committed in source code.",
        severity="HIGH",
        category="SECURITY",
        file_path="app/config/keys.py",
        line_start=12,
        line_end=12,
        confidence=0.9,
        status="OPEN",
        impact="Credential leakage",
        recommendation="Store secret in environment variables or vault.",
        policy_reference="SEC-CRED-01",
        fingerprint="fp-secret-002",
    )
    f3 = Finding(
        review_run_id=run.id,
        title="Cognitive Complexity Exceeded",
        description="Function process_payment has cyclomatic complexity of 24.",
        severity="LOW",
        category="QUALITY",
        file_path="app/services/payment.py",
        line_start=100,
        line_end=150,
        confidence=0.8,
        status="OPEN",
        impact="Maintainability issue",
        recommendation="Refactor into smaller handler functions.",
        policy_reference="QUAL-COMPLEX-01",
        fingerprint="fp-complex-003",
    )
    test_db_session.add_all([f1, f2, f3])
    await test_db_session.commit()
    await test_db_session.refresh(run)

    return run


def build_sample_report(pr_number: int = 101, is_mergeable: bool = False, grade: RiskGrade = RiskGrade.D) -> ReviewReport:
    """Builds a memory ReviewReport object for unit testing formatting methods."""
    risk_level = (
        RiskLevel.CRITICAL if grade == RiskGrade.F
        else (RiskLevel.HIGH if grade in [RiskGrade.C, RiskGrade.D] else RiskLevel.LOW)
    )
    summary = ReviewReportSummary(
        review_run_id="run-test-123",
        repo_name="codeguardian-corp/secure-microservice",
        pr_number=pr_number,
        pr_title="feat: Payment processing and auth endpoints",
        author="lead-dev",
        source_branch="feat/payment-auth",
        target_branch="main",
        commit_sha="e7a4b1c2d3e4f56789012345678901234567890a",
        risk_score=78.5,
        risk_grade=grade,
        risk_level=risk_level,
        is_mergeable=is_mergeable,
        recommended_action="REVISE_REQUIRED" if not is_mergeable else "APPROVE",
        total_findings=3,
        critical_count=1 if not is_mergeable else 0,
        high_count=1,
        medium_count=0,
        low_count=1,
        info_count=0,
        duration_ms=450,
    )
    breakdown = CategoryRiskBreakdown(
        security=90.0,
        quality=40.0,
        testing=20.0,
        documentation=10.0,
        dependency=0.0,
    )
    findings = [
        ReportFindingItem(
            finding_id="f-1",
            fingerprint="fp-1",
            title="SQL Injection Vulnerability",
            description="Raw string formatting in SQL query.",
            severity="CRITICAL",
            category="SECURITY",
            confidence=1.0,
            file_path="app/api/payments.py",
            line_start=45,
            line_end=48,
            recommendation="Use parameterized query.",
            policy_reference="SEC-SQL-01",
        ),
        ReportFindingItem(
            finding_id="f-2",
            fingerprint="fp-2",
            title="Hardcoded API Secret",
            description="Plaintext Stripe secret key committed.",
            severity="HIGH",
            category="SECURITY",
            confidence=0.9,
            file_path="app/config/keys.py",
            line_start=12,
            line_end=12,
            recommendation="Use environment variables.",
            policy_reference="SEC-CRED-01",
        ),
    ]
    return ReviewReport(
        summary=summary,
        category_breakdown=breakdown,
        agent_summaries=[],
        findings=findings,
        risk_driving_factors=["Critical SQL Injection detected in payments API"],
        markdown_content="## Sample Markdown Content",
    )



# 1. Format & Marker Tests
def test_comment_marker_generation_and_format():
    marker = GitHubReporter.generate_comment_marker(101)
    assert marker == "<!-- codeguardian-pr-review-summary:pr-101 -->"
    assert COMMENT_MARKER_PREFIX in marker

    report = build_sample_report(pr_number=101, is_mergeable=False, grade=RiskGrade.D)
    comment = GitHubReporter.format_pr_review_comment(report)

    # Must contain the marker at the start for anti-spam detection
    assert comment.startswith(marker)
    assert "CodeGuardian AI — Pull Request DevSecOps Review" in comment
    assert "GRADE D" in comment
    assert "MERGE BLOCKED" in comment
    assert "78.5/100" in comment
    assert "| **3** | **1** | **1** | **0** | **1** | **0** |" in comment
    assert "Category Risk Radar" in comment
    assert "Severe Findings Requiring Action" in comment
    assert "SQL Injection Vulnerability" in comment


# 2. Check Run Annotations Tests
def test_build_check_run_annotations():
    f_crit = Finding(
        title="Remote Code Execution",
        description="Unsafe deserialization",
        severity="CRITICAL",
        category="SECURITY",
        file_path="app/worker.py",
        line_start=15,
        line_end=16,
        recommendation="Use safe loader.",
        policy_reference="SEC-DESER-01",
        fingerprint="fp-crit",
    )
    f_high = Finding(
        title="Missing Auth",
        description="Endpoint unauthenticated",
        severity="HIGH",
        category="SECURITY",
        file_path="app/api.py",
        line_start=None,  # Should clamp to 1
        line_end=None,
        recommendation="Add auth dependency.",
        policy_reference=None,
        fingerprint="fp-high",
    )
    f_info = Finding(
        title="Unused Import",
        description="Unused sys import",
        severity="INFO",
        category="QUALITY",
        file_path="app/util.py",
        line_start=3,
        line_end=3,
        recommendation="Remove import.",
        policy_reference=None,
        fingerprint="fp-info",
    )

    annotations = GitHubReporter.build_check_run_annotations([f_info, f_crit, f_high])

    assert len(annotations) == 3
    # Critical should be sorted first
    assert annotations[0]["annotation_level"] == "failure"
    assert annotations[0]["title"] == "[CRITICAL] Remote Code Execution"
    assert annotations[0]["start_line"] == 15
    assert annotations[0]["end_line"] == 16

    # High should be second
    assert annotations[1]["annotation_level"] == "warning"
    assert annotations[1]["start_line"] == 1
    assert annotations[1]["end_line"] == 1

    # Info should be third
    assert annotations[2]["annotation_level"] == "notice"
    assert annotations[2]["path"] == "app/util.py"


# 3. Check Run Conclusion Determination
@pytest.mark.asyncio
async def test_publish_check_run_conclusions():
    mock_client = MagicMock(spec=GitHubClient)
    mock_client.create_check_run = AsyncMock(return_value={"id": 888, "status": "completed"})
    reporter = GitHubReporter(client=mock_client)

    # Case A: Failing report (unmergeable, criticals)
    failing_report = build_sample_report(is_mergeable=False, grade=RiskGrade.F)
    res_fail = await reporter.publish_check_run("codeguardian-corp", "secure-microservice", failing_report)
    assert res_fail["id"] == 888
    call_args_fail = mock_client.create_check_run.call_args[1]
    assert call_args_fail["conclusion"] == "failure"

    # Case B: Clean passing report
    passing_report = build_sample_report(is_mergeable=True, grade=RiskGrade.A)
    passing_report.summary.critical_count = 0
    passing_report.summary.high_count = 0
    passing_report.summary.is_mergeable = True
    await reporter.publish_check_run("codeguardian-corp", "secure-microservice", passing_report)
    call_args_pass = mock_client.create_check_run.call_args[1]
    assert call_args_pass["conclusion"] == "success"


# 4. Anti-Spam Deduplication Tests
@pytest.mark.asyncio
async def test_publish_or_update_pr_comment_anti_spam():
    mock_client = MagicMock(spec=GitHubClient)
    reporter = GitHubReporter(client=mock_client)
    report = build_sample_report(pr_number=101)

    # Sub-case 1: No previous review comment exists -> CREATE new comment
    mock_client.list_issue_comments = AsyncMock(return_value=[
        {"id": 501, "body": "LGTM from collaborator!"},
        {"id": 502, "body": "Could you add more unit tests?"},
    ])
    mock_client.create_issue_comment = AsyncMock(return_value={"id": 503, "body": "review comment"})

    res_create = await reporter.publish_or_update_pr_comment("owner", "repo", report)
    assert res_create["action"] == "CREATED"
    assert res_create["comment_id"] == 503
    mock_client.create_issue_comment.assert_called_once()

    # Sub-case 2: Existing review comment with anti-spam marker exists -> UPDATE in-place
    mock_client.list_issue_comments = AsyncMock(return_value=[
        {"id": 501, "body": "LGTM from collaborator!"},
        {"id": 505, "body": "<!-- codeguardian-pr-review-summary:pr-101 -->\n## Old CodeGuardian Review"},
    ])
    mock_client.update_issue_comment = AsyncMock(return_value={"id": 505, "body": "updated review comment"})

    res_update = await reporter.publish_or_update_pr_comment("owner", "repo", report)
    assert res_update["action"] == "UPDATED"
    assert res_update["comment_id"] == 505
    mock_client.update_issue_comment.assert_called_once()


# 5. Full Pipeline & Mock Token Fallback
@pytest.mark.asyncio
async def test_publish_review_report_mock_fallback(test_db_session: AsyncSession, seeded_review_run: ReviewRun):
    # When token is unset or "mock_...", safely returns simulated result
    client = GitHubClient(token="mock_token_abc")
    reporter = GitHubReporter(client=client)

    result = await reporter.publish_review_report(test_db_session, seeded_review_run.id)
    assert isinstance(result, GitHubPublishResult)
    assert result.status == "PUBLISHED"
    assert result.check_run_id == 1001
    assert result.comment_id == 2001
    assert "Mock delivery" in (result.details or "")


# 6. Full Pipeline Live Mocked Publishing
@pytest.mark.asyncio
async def test_publish_review_report_live_mocked(test_db_session: AsyncSession, seeded_review_run: ReviewRun):
    mock_client = MagicMock(spec=GitHubClient)
    mock_client.token = "ghp_real_authorized_token_12345"
    mock_client.create_check_run = AsyncMock(return_value={"id": 9001, "conclusion": "failure"})
    mock_client.list_issue_comments = AsyncMock(return_value=[])
    mock_client.create_issue_comment = AsyncMock(return_value={"id": 9002, "body": "review comment"})
    mock_client.create_pull_request_review_comment = AsyncMock(return_value={"id": 9003})

    reporter = GitHubReporter(client=mock_client)
    result = await reporter.publish_review_report(test_db_session, seeded_review_run.id)

    assert result.status == "PUBLISHED"
    assert result.check_run_id == 9001
    assert result.check_run_conclusion == "failure"
    assert result.comment_id == 9002
    assert result.comment_action == "CREATED"
    assert result.inline_comments_count == 1  # 1 critical finding has line_start=45


# 7. Dry-Run Preview Service
@pytest.mark.asyncio
async def test_preview_github_report_service(test_db_session: AsyncSession, seeded_review_run: ReviewRun):
    reporter = GitHubReporter()
    preview = await reporter.preview_github_report(test_db_session, seeded_review_run.id)

    assert isinstance(preview, GitHubReportPreview)
    assert preview.review_run_id == seeded_review_run.id
    assert preview.pr_number == 101
    assert preview.check_run_conclusion == "failure"
    assert "<!-- codeguardian-pr-review-summary:pr-101 -->" in preview.comment_markdown
    assert preview.annotations_count == 3
    assert len(preview.annotations) > 0


# 8. REST API Endpoints Verification
@pytest.mark.asyncio
async def test_github_reporting_api_endpoints(test_db_session: AsyncSession, seeded_review_run: ReviewRun):
    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Preview endpoint
            resp_prev = await client.get(f"/api/v1/reviews/{seeded_review_run.id}/github/preview")
            assert resp_prev.status_code == 200
            data_prev = resp_prev.json()
            assert data_prev["review_run_id"] == seeded_review_run.id
            assert data_prev["pr_number"] == 101
            assert "CodeGuardian AI — Pull Request DevSecOps Review" in data_prev["comment_markdown"]
            assert data_prev["annotations_count"] == 3

            # 2. Publish endpoint (mock fallback active in test)
            resp_pub = await client.post(f"/api/v1/reviews/{seeded_review_run.id}/github/publish")
            assert resp_pub.status_code == 200
            data_pub = resp_pub.json()
            assert data_pub["review_run_id"] == seeded_review_run.id
            assert data_pub["status"] == "PUBLISHED"
            assert data_pub["check_run_id"] is not None

            # 3. 404 on invalid review run ID
            resp_404 = await client.get("/api/v1/reviews/non-existent-uuid/github/preview")
            assert resp_404.status_code == 404

    finally:
        app.dependency_overrides.clear()
