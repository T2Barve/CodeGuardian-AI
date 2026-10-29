import os
import tempfile
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.findings.correlation import CorrelatedFinding
from app.main import app
from app.models.finding import Finding
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob, ReviewRun
from app.repositories.finding_repository import FindingRepository
from app.repositories.pull_request_repository import PullRequestRepository
from app.repositories.repository_repository import RepositoryRepository
from app.repositories.review_repository import ReviewJobRepository, ReviewRunRepository
from app.risk.engine import RiskEngine
from app.risk.service import RiskService
from app.schemas.queue import ReviewJobPayload
from app.schemas.risk import (
    CategoryRiskBreakdown,
    FindingRiskInput,
    RepositoryRiskProfile,
    RepositoryTier,
    RiskActionRecommendation,
    RiskAssessment,
    RiskCalculationRequest,
    RiskGrade,
    RiskLevel,
)
from app.workers.queue import MemoryReviewQueue
from app.workers.review_worker import ReviewWorker


# ==============================================================================
# 1. MATHEMATICAL DETERMINISM & BOUNDARY TESTS
# ==============================================================================


def test_zero_findings_produces_clean_grade_a():
    """Validates that a review with 0 findings evaluates to a perfect 0.0 Grade A score."""
    assessment = RiskEngine.calculate_risk(findings=[])
    assert assessment.overall_score == 0.0
    assert assessment.grade == RiskGrade.A
    assert assessment.level == RiskLevel.LOW
    assert assessment.action == RiskActionRecommendation.APPROVE
    assert assessment.is_mergeable is True
    assert assessment.breakdown.security == 0.0
    assert assessment.breakdown.quality == 0.0
    assert len(assessment.factors) > 0


def test_deterministic_invariance():
    """Validates that evaluating the exact same findings 50 times produces identical numerical results."""
    findings = [
        {"severity": "HIGH", "category": "SECURITY", "confidence": 0.95},
        {"severity": "MEDIUM", "category": "QUALITY", "confidence": 0.85},
        {"severity": "LOW", "category": "TESTING", "confidence": 1.0},
    ]

    first = RiskEngine.calculate_risk(findings)
    for _ in range(50):
        subsequent = RiskEngine.calculate_risk(findings)
        assert subsequent.overall_score == first.overall_score
        assert subsequent.grade == first.grade
        assert subsequent.breakdown.security == first.breakdown.security
        assert subsequent.breakdown.quality == first.breakdown.quality


def test_single_low_and_medium_findings():
    """Validates that low/medium findings remain in Grade A/B tier."""
    # 1 Low finding (3.0 base * 1.0 conf * 1.2 security factor = 3.6)
    low_assessment = RiskEngine.calculate_risk(
        [{"severity": "LOW", "category": "SECURITY", "confidence": 1.0}]
    )
    assert low_assessment.overall_score == 3.6
    assert low_assessment.grade == RiskGrade.A
    assert low_assessment.action == RiskActionRecommendation.APPROVE
    assert low_assessment.is_mergeable is True

    # 1 Medium finding (8.0 base * 1.0 conf * 1.2 security = 9.6)
    med_assessment = RiskEngine.calculate_risk(
        [{"severity": "MEDIUM", "category": "SECURITY", "confidence": 1.0}]
    )
    assert med_assessment.overall_score == 9.6
    assert med_assessment.grade == RiskGrade.A

    # 2 Medium findings (19.2 -> Grade B)
    two_med = RiskEngine.calculate_risk(
        [
            {"severity": "MEDIUM", "category": "SECURITY", "confidence": 1.0},
            {"severity": "MEDIUM", "category": "SECURITY", "confidence": 1.0},
        ]
    )
    assert two_med.overall_score == 19.2
    assert two_med.grade == RiskGrade.B
    assert two_med.action == RiskActionRecommendation.APPROVE_WITH_SUGGESTIONS
    assert two_med.is_mergeable is True


def test_critical_finding_override_rules():
    """
    Validates non-negotiable blocker rules:
    - Exactly 1 Critical finding -> minimum score 70.0 (Grade D, Request Changes).
    - 2 or more Critical findings -> minimum score 86.0 (Grade F, Block Merge).
    """
    one_crit = RiskEngine.calculate_risk(
        [{"severity": "CRITICAL", "category": "SECURITY", "confidence": 1.0}]
    )
    assert one_crit.overall_score >= 70.0
    assert one_crit.grade in (RiskGrade.D, RiskGrade.F)
    assert one_crit.action in (RiskActionRecommendation.REQUEST_CHANGES, RiskActionRecommendation.BLOCK)
    assert one_crit.is_mergeable is False

    two_crits = RiskEngine.calculate_risk(
        [
            {"severity": "CRITICAL", "category": "SECURITY", "confidence": 0.8},
            {"severity": "CRITICAL", "category": "SECURITY", "confidence": 0.8},
        ]
    )
    assert two_crits.overall_score >= 86.0
    assert two_crits.grade == RiskGrade.F
    assert two_crits.level == RiskLevel.CRITICAL
    assert two_crits.action == RiskActionRecommendation.BLOCK
    assert two_crits.is_mergeable is False


def test_score_clamping_at_100():
    """Validates that a massive volume of severe vulnerabilities does not overflow past 100.0."""
    massive_findings = [
        {"severity": "CRITICAL", "category": "SECURITY", "confidence": 1.0}
        for _ in range(20)
    ]
    assessment = RiskEngine.calculate_risk(massive_findings)
    assert assessment.overall_score == 100.0
    assert assessment.grade == RiskGrade.F
    assert assessment.is_mergeable is False


# ==============================================================================
# 2. CATEGORY RADAR BREAKDOWN & REPO PROFILES
# ==============================================================================


def test_category_radar_breakdown():
    """Validates multi-dimensional category sub-scores across security, quality, test, doc, dependency."""
    mixed_findings = [
        {"severity": "HIGH", "category": "SECURITY", "confidence": 1.0},       # 15 * 1.2 = 18.0
        {"severity": "MEDIUM", "category": "QUALITY", "confidence": 1.0},        # 8 * 0.9 = 7.2
        {"severity": "MEDIUM", "category": "TESTING", "confidence": 1.0},        # 8 * 1.0 = 8.0
        {"severity": "LOW", "category": "DOCUMENTATION", "confidence": 1.0},     # 3 * 0.5 = 1.5
        {"severity": "HIGH", "category": "DEPENDENCY", "confidence": 1.0},       # 15 * 1.1 = 16.5
    ]
    assessment = RiskEngine.calculate_risk(mixed_findings)

    assert assessment.breakdown.security == 18.0
    assert assessment.breakdown.quality == 7.2
    assert assessment.breakdown.testing == 8.0
    assert assessment.breakdown.documentation == 1.5
    assert assessment.breakdown.dependency == 16.5
    assert assessment.findings_count_by_category["SECURITY"] == 1
    assert assessment.findings_count_by_category["QUALITY"] == 1


def test_repository_criticality_tiers():
    """Validates that repository tier multipliers scale the risk score appropriately."""
    findings = [{"severity": "HIGH", "category": "SECURITY", "confidence": 1.0}]  # Base 18.0

    tier1_profile = RepositoryRiskProfile.from_tier(RepositoryTier.TIER_1)  # 1.25x
    tier2_profile = RepositoryRiskProfile.from_tier(RepositoryTier.TIER_2)  # 1.0x
    tier3_profile = RepositoryRiskProfile.from_tier(RepositoryTier.TIER_3)  # 0.8x

    res1 = RiskEngine.calculate_risk(findings, repo_profile=tier1_profile)
    res2 = RiskEngine.calculate_risk(findings, repo_profile=tier2_profile)
    res3 = RiskEngine.calculate_risk(findings, repo_profile=tier3_profile)

    assert res1.overall_score == round(18.0 * 1.25, 2)  # 22.5
    assert res2.overall_score == 18.0
    assert res3.overall_score == round(18.0 * 0.8, 2)   # 14.4

    # Non-production branch discounts by an additional 0.9x
    non_prod_profile = RepositoryRiskProfile(tier=RepositoryTier.TIER_2, criticality_multiplier=1.0, is_production=False)
    res_non_prod = RiskEngine.calculate_risk(findings, repo_profile=non_prod_profile)
    assert res_non_prod.overall_score == round(18.0 * 0.9, 2)  # 16.2


def test_pr_churn_penalty():
    """Validates that high lines changed and broad file counts penalize the score."""
    findings = [{"severity": "LOW", "category": "QUALITY", "confidence": 1.0}]  # Base: 3 * 0.9 = 2.7

    normal_pr = RiskEngine.calculate_risk(findings, lines_changed=50, files_changed=2)
    assert normal_pr.overall_score == 2.7

    large_pr = RiskEngine.calculate_risk(findings, lines_changed=1200, files_changed=30)
    # 2.7 + 5.0 (lines > 1000) + 2.0 (files > 25) = 9.7
    assert large_pr.overall_score == 9.7


def test_input_type_versatility():
    """Validates that dicts, FindingRiskInput, and CorrelatedFinding objects produce identical results."""
    raw_dict = {"severity": "HIGH", "category": "SECURITY", "confidence": 0.9}
    pydantic_in = FindingRiskInput(severity="HIGH", category="SECURITY", confidence=0.9)
    correlated_in = CorrelatedFinding(
        fingerprint="abc",
        category="SECURITY",
        severity="HIGH",
        confidence=0.9,
        file_path="src/main.py",
        line_start=10,
        line_end=12,
        title="SQLi",
        description="SQL injection",
        impact="Data leak",
        recommendation="Sanitize input",
        policy_reference="SEC-01",
    )

    score_dict = RiskEngine.calculate_risk([raw_dict]).overall_score
    score_pydantic = RiskEngine.calculate_risk([pydantic_in]).overall_score
    score_correlated = RiskEngine.calculate_risk([correlated_in]).overall_score

    assert score_dict == score_pydantic
    assert score_dict == score_correlated


# ==============================================================================
# 3. DATABASE SERVICE PERSISTENCE TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_risk_service_assess_and_persist(db_session: AsyncSession):
    """Validates persisting risk assessment directly to the PostgreSQL ReviewRun record."""
    repo_repository = RepositoryRepository(db_session)
    pr_repository = PullRequestRepository(db_session)
    job_repository = ReviewJobRepository(db_session)
    run_repository = ReviewRunRepository(db_session)
    finding_repository = FindingRepository(db_session)

    # 1. Create parent entities
    repo = await repo_repository.create(
        github_repo_id=98765432,
        name="test-org/risk-repo",
        owner="test-org",
        url="https://github.com/test-org/risk-repo",
        default_branch="main",
    )
    pr = await pr_repository.create(
        github_pr_id=12345,
        repository_id=repo.id,
        number=88,
        title="Payment Gateway Integration",
        author="alice",
        source_branch="feature/payments",
        target_branch="main",
        commit_sha="d9e8f7a6b5c4",
    )
    job = await job_repository.create(pull_request_id=pr.id, status="RUNNING")
    review_run = await run_repository.create(
        review_job_id=job.id,
        status="RUNNING",
        configuration={"repo_tier": "TIER_1"},
    )

    # 2. Insert mock findings in database
    await finding_repository.create(
        review_run_id=review_run.id,
        fingerprint="fp1",
        category="SECURITY",
        severity="CRITICAL",
        confidence=0.95,
        status="OPEN",
        file_path="src/payments.py",
        line_start=40,
        title="Payment Bypass",
        description="Insecure payment validation logic",
    )
    await finding_repository.create(
        review_run_id=review_run.id,
        fingerprint="fp2",
        category="QUALITY",
        severity="MEDIUM",
        confidence=0.90,
        status="OPEN",
        file_path="src/utils.py",
        line_start=15,
        title="Complex Method",
        description="Method exceeds cyclomatic complexity threshold",
    )
    await db_session.commit()

    # 3. Assess and persist risk
    assessment = await RiskService.assess_and_persist_review_risk(
        session=db_session,
        review_run_id=review_run.id,
    )

    assert assessment.overall_score >= 70.0
    assert assessment.grade in (RiskGrade.D, RiskGrade.F)
    assert assessment.is_mergeable is False

    # 4. Verify updated ReviewRun entity in database
    refreshed_run = await run_repository.get(review_run.id)
    assert refreshed_run is not None
    assert refreshed_run.risk_score == assessment.overall_score
    assert refreshed_run.risk_grade == assessment.grade.value
    assert "risk_assessment" in refreshed_run.configuration
    assert refreshed_run.configuration["risk_assessment"]["overall_score"] == assessment.overall_score


# ==============================================================================
# 4. REST API ENDPOINTS TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_risk_api_endpoints(db_session: AsyncSession):
    """Validates GET /api/v1/reviews/{id}/risk and POST /api/v1/risk/calculate."""
    repo_repository = RepositoryRepository(db_session)
    pr_repository = PullRequestRepository(db_session)
    job_repository = ReviewJobRepository(db_session)
    run_repository = ReviewRunRepository(db_session)

    # Setup ReviewRun
    repo = await repo_repository.create(
        github_repo_id=11223344,
        name="test-org/api-risk-repo",
        owner="test-org",
        url="https://github.com/test-org/api-risk-repo",
        default_branch="main",
    )
    pr = await pr_repository.create(
        github_pr_id=112233,
        repository_id=repo.id,
        number=99,
        title="API Risk Test",
        author="bob",
        source_branch="test",
        target_branch="main",
        commit_sha="abcdef123456",
    )
    job = await job_repository.create(pull_request_id=pr.id, status="RUNNING")
    review_run = await run_repository.create(
        review_job_id=job.id,
        status="SUCCESS",
        risk_score=12.5,
        risk_grade="A",
        configuration={
            "risk_assessment": {
                "overall_score": 12.5,
                "grade": "A",
                "level": "LOW",
                "action": "APPROVE",
                "is_mergeable": True,
                "breakdown": {
                    "security": 10.0,
                    "quality": 2.5,
                    "testing": 0.0,
                    "documentation": 0.0,
                    "dependency": 0.0,
                },
                "findings_count_by_severity": {"LOW": 2},
                "findings_count_by_category": {"SECURITY": 1, "QUALITY": 1},
                "factors": ["Clean PR"],
                "assessed_at": "2026-10-03T10:00:00Z",
            }
        },
    )
    await db_session.commit()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. GET existing review risk
            res = await client.get(f"/api/v1/reviews/{review_run.id}/risk")
            assert res.status_code == 200
            data = res.json()
            assert data["overall_score"] == 12.5
            assert data["grade"] == "A"
            assert data["is_mergeable"] is True
            assert data["breakdown"]["security"] == 10.0

            # 2. GET non-existent review risk
            res_404 = await client.get("/api/v1/reviews/non-existent-uuid/risk")
            assert res_404.status_code == 404
            assert res_404.json()["type"] == "urn:problem:review-run-not-found"

            # 3. POST stateless risk calculation
            stateless_payload = {
                "findings": [
                    {"severity": "HIGH", "category": "SECURITY", "confidence": 1.0},
                    {"severity": "MEDIUM", "category": "QUALITY", "confidence": 0.9},
                ],
                "repo_tier": "TIER_1",
                "lines_changed": 150,
            }
            res_calc = await client.post("/api/v1/risk/calculate", json=stateless_payload)
            assert res_calc.status_code == 200
            calc_data = res_calc.json()
            assert calc_data["overall_score"] > 0
            assert calc_data["grade"] in ("B", "C")
            assert "factors" in calc_data
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 5. WORKER END-TO-END RISK SCORING EXECUTION
# ==============================================================================


@pytest.mark.asyncio
async def test_worker_end_to_end_scanning_findings_and_risk_scoring(db_session: AsyncSession):
    """
    Validates complete worker pipeline:
    PR scan -> findings correlated -> findings persisted -> risk score computed and persisted to ReviewRun.
    """
    queue = MemoryReviewQueue()
    worker = ReviewWorker(
        queue=queue,
        session_factory=lambda: db_session,
    )

    repo_repository = RepositoryRepository(db_session)
    pr_repository = PullRequestRepository(db_session)
    job_repository = ReviewJobRepository(db_session)
    run_repository = ReviewRunRepository(db_session)

    repo = await repo_repository.create(
        github_repo_id=77889900,
        name="test-org/e2e-risk-repo",
        owner="test-org",
        url="https://github.com/test-org/e2e-risk-repo",
        default_branch="main",
    )
    pr = await pr_repository.create(
        github_pr_id=778899,
        repository_id=repo.id,
        number=55,
        title="Vulnerable Feature Branch",
        author="charlie",
        source_branch="feature/vuln",
        target_branch="main",
        commit_sha="1a2b3c4d5e6f",
    )
    job = await job_repository.create(pull_request_id=pr.id, status="QUEUED")
    await db_session.commit()

    # Create temporary repo directory with intentional vulnerability (SQLi)
    with tempfile.TemporaryDirectory() as tmp_dir:
        src_dir = os.path.join(tmp_dir, "src")
        os.makedirs(src_dir, exist_ok=True)
        py_file = os.path.join(src_dir, "db.py")
        with open(py_file, "w", encoding="utf-8") as f:
            f.write(
                'import sqlite3\n'
                'def get_user(user_id):\n'
                '    conn = sqlite3.connect("app.db")\n'
                '    query = "SELECT * FROM users WHERE id = \'" + user_id + "\'"\n'
                '    return conn.execute(query).fetchall()\n'
            )

        payload = ReviewJobPayload(
            job_id=job.id,
            pull_request_id=pr.id,
            repo_name=repo.name,
            repo_owner=repo.owner,
            pr_number=pr.number,
            commit_sha=pr.commit_sha,
            metadata={
                "workspace_path": tmp_dir,
                "lines_changed": 5,
                "files_changed": 1,
            },
        )
        await queue.enqueue_review(payload)

        # Process job via worker
        processed = await worker.run_once()
        assert processed is True

    # Validate that ReviewRun has risk score and grade persisted
    review_run = await run_repository.get_by_job_id(job.id)
    assert review_run is not None
    assert review_run.status == "SUCCESS"
    assert review_run.risk_score is not None
    assert review_run.risk_grade in ("A", "B", "C", "D", "F")
    assert "risk_assessment" in review_run.configuration
    assert review_run.configuration["risk_assessment"]["overall_score"] == review_run.risk_score
    assert "Grade" in review_run.summary
