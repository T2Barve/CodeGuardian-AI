import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database.session import get_db
from app.findings.service import FindingService
from app.main import app
from app.models.base import Base
from app.models.finding import Finding
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob, ReviewRun
from app.models.user import User
from app.reports.generator import ReportGenerator
from app.reports.service import ReportService
from app.risk.service import RiskService
from app.schemas.report import (
    ReportAgentSummary,
    ReportFindingItem,
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
    # Seed User, Repo, PR, Job, Run
    user = User(
        username="darshan-dev",
        email="darshan@example.com",
        github_id="gh_12345",
        role="DEVELOPER",
    )
    test_db_session.add(user)
    await test_db_session.flush()

    repo = Repository(
        github_repo_id=987654,
        name="codeguardian-ai",
        owner="codeguardian",
        url="https://github.com/codeguardian/codeguardian-ai",
        default_branch="main",
        language="python",
        is_active=True,
    )
    test_db_session.add(repo)
    await test_db_session.flush()

    pr = PullRequest(
        github_pr_id=123456,
        repository_id=repo.id,
        number=42,
        title="feat: Add database connection pool and user search",
        author="darshan-dev",
        source_branch="feature/user-search",
        target_branch="main",
        commit_sha="a1b2c3d4e5f67890",
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
        status="RUNNING",
        duration_ms=1850,
        configuration={},
    )
    test_db_session.add(run)
    await test_db_session.flush()

    # Add a sample finding
    finding = Finding(
        review_run_id=run.id,
        fingerprint="sha256_mock_fingerprint_sql_injection",
        category="SECURITY",
        severity="CRITICAL",
        confidence=0.95,
        status="OPEN",
        file_path="apps/backend/app/db/search.py",
        line_start=45,
        line_end=48,
        title="SQL Injection via Dynamic String Formatting",
        description="Untrusted user parameter directly formatted into raw SQL query.",
        impact="Full unauthorized database extraction or modification.",
        recommendation="Use parameterized statements via SQLAlchemy ORM.",
        policy_reference="SEC-002 Database Security Baseline",
    )
    test_db_session.add(finding)
    await test_db_session.commit()
    await test_db_session.refresh(run)

    return run


# ==============================================================================
# 1. REPORT GENERATOR UNIT TESTS
# ==============================================================================

def test_report_generator_clean_pr_markdown():
    summary = ReviewReportSummary(
        review_run_id="run_clean_1",
        job_id="job_clean_1",
        repo_name="org/clean-service",
        pr_number=10,
        pr_title="docs: Update system documentation",
        author="tanishq-ai",
        commit_sha="9876543210abcdef",
        source_branch="docs/update",
        target_branch="main",
        risk_score=0.0,
        risk_grade=RiskGrade.A,
        risk_level=RiskLevel.LOW,
        is_mergeable=True,
        recommended_action="APPROVE",
        duration_ms=450,
        total_findings=0,
        critical_count=0,
        high_count=0,
        medium_count=0,
        low_count=0,
        info_count=0,
    )
    cat_breakdown = CategoryRiskBreakdown(
        security=0.0, quality=0.0, testing=0.0, documentation=0.0, dependency=0.0
    )

    report = ReportGenerator.assemble_report(
        summary=summary,
        category_breakdown=cat_breakdown,
        risk_driving_factors=[],
        findings=[],
    )

    assert report.summary.risk_grade == RiskGrade.A
    assert report.summary.is_mergeable is True
    assert "GRADE A" in report.markdown_content
    assert "MERGEABLE" in report.markdown_content
    assert "No security vulnerabilities, quality defects" in report.markdown_content


def test_report_generator_critical_pr_markdown():
    summary = ReviewReportSummary(
        review_run_id="run_crit_1",
        job_id="job_crit_1",
        repo_name="org/backend-api",
        pr_number=88,
        pr_title="feat: Quick login route",
        author="mayur-backend",
        commit_sha="fedcba0987654321",
        source_branch="feature/login",
        target_branch="main",
        risk_score=85.0,
        risk_grade=RiskGrade.F,
        risk_level=RiskLevel.CRITICAL,
        is_mergeable=False,
        recommended_action="BLOCK",
        duration_ms=2100,
        total_findings=1,
        critical_count=1,
        high_count=0,
        medium_count=0,
        low_count=0,
        info_count=0,
    )
    cat_breakdown = CategoryRiskBreakdown(
        security=85.0, quality=0.0, testing=0.0, documentation=0.0, dependency=0.0
    )
    finding = ReportFindingItem(
        finding_id="find_sqli_1",
        fingerprint="sha256_mock_1",
        category="SECURITY",
        severity="CRITICAL",
        confidence=0.98,
        file_path="app/auth.py",
        line_start=12,
        line_end=15,
        title="Raw SQL Injection in Login",
        description="Password formatted directly into SELECT query.",
        impact="Authentication bypass.",
        recommendation="Use bcrypt + parameterized query.",
        code_snippet="query = f'SELECT * FROM users WHERE pass = {p}'",
        policy_reference="SEC-001 Secure Coding Baseline",
        tools_involved=["Bandit", "Semgrep"],
    )
    agents = [
        ReportAgentSummary(
            agent_name="SecurityAgent",
            status="COMPLETED",
            duration_ms=350,
            token_usage=180,
            findings_count=1,
        )
    ]

    report = ReportGenerator.assemble_report(
        summary=summary,
        category_breakdown=cat_breakdown,
        risk_driving_factors=["Critical security vulnerability detected"],
        findings=[finding],
        agent_summaries=agents,
    )

    md = report.markdown_content
    assert "GRADE F" in md
    assert "BLOCKED" in md
    assert "Raw SQL Injection in Login" in md
    assert "Bandit, Semgrep" in md
    assert "SEC-001 Secure Coding Baseline" in md
    assert "<details><summary><b>View Affected Code Snippet</b></summary>" in md
    assert "SecurityAgent" in md


# ==============================================================================
# 2. REPORT SERVICE & PERSISTENCE TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_report_service_generate_and_persist(
    test_db_session: AsyncSession, seeded_review_run: ReviewRun
):
    # First assess risk to populate risk configuration
    await RiskService.assess_and_persist_review_risk(
        session=test_db_session,
        review_run_id=seeded_review_run.id,
    )

    service = ReportService()
    report = await service.generate_and_persist_report(
        session=test_db_session,
        review_run_id=seeded_review_run.id,
    )

    assert report is not None
    assert report.summary.repo_name == "codeguardian-ai"
    assert report.summary.pr_number == 42
    assert report.summary.total_findings == 1
    assert report.summary.critical_count == 1
    assert report.summary.is_mergeable is False
    assert report.markdown_content is not None
    assert "SQL Injection via Dynamic String Formatting" in report.markdown_content

    # Verify report is retrievable from DB
    retrieved = await service.get_report(test_db_session, seeded_review_run.id)
    assert retrieved is not None
    assert retrieved.summary.review_run_id == seeded_review_run.id


# ==============================================================================
# 3. REST API ENDPOINTS TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_report_rest_api_endpoints(
    test_db_session: AsyncSession, seeded_review_run: ReviewRun
):
    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Generate report via API
        res_gen = await client.post(f"/api/v1/reviews/{seeded_review_run.id}/report/generate")
        assert res_gen.status_code == 201
        data = res_gen.json()
        assert data["summary"]["pr_number"] == 42
        assert data["summary"]["critical_count"] == 1

        # 2. Get JSON report
        res_get = await client.get(f"/api/v1/reviews/{seeded_review_run.id}/report")
        assert res_get.status_code == 200
        get_data = res_get.json()
        assert get_data["summary"]["repo_name"] == "codeguardian-ai"

        # 3. Get Markdown report
        res_md = await client.get(f"/api/v1/reviews/{seeded_review_run.id}/report/markdown")
        assert res_md.status_code == 200
        assert res_md.headers["content-type"].startswith("text/markdown")
        md_text = res_md.text
        assert "CodeGuardian AI — Pull Request Review Report" in md_text
        assert "SQL Injection via Dynamic String Formatting" in md_text

        # 4. 404 for invalid ID
        res_404 = await client.get("/api/v1/reviews/non-existent-uuid/report")
        assert res_404.status_code == 500 or res_404.status_code == 404

    app.dependency_overrides.clear()
