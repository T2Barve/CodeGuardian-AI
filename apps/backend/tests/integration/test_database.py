import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.user import User
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.review import ReviewJob, ReviewRun
from app.models.finding import Finding, FindingEvidence
from app.models.agent import AgentRun
from app.models.policy import Policy, PolicyChunk
from app.models.remediation import RemediationAttempt, FixPR
from app.models.audit import AuditLog

from app.repositories.user_repository import UserRepository
from app.repositories.repository_repository import RepositoryRepository
from app.repositories.pull_request_repository import PullRequestRepository
from app.repositories.review_repository import ReviewJobRepository, ReviewRunRepository
from app.repositories.finding_repository import FindingRepository, FindingEvidenceRepository
from app.repositories.policy_repository import PolicyRepository, PolicyChunkRepository
from app.repositories.remediation_repository import RemediationRepository, FixPRRepository
from app.repositories.audit_repository import AuditRepository


@pytest.fixture(scope="function")
async def test_session():
    """Provides a fresh isolated in-memory SQLite database session for each test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_user_repository_crud(test_session: AsyncSession):
    repo = UserRepository(test_session)
    user = await repo.create(
        github_id=99991,
        username="darshan-test",
        email="darshan@test.com",
        role="DEVELOPER",
    )
    assert user.id is not None
    assert user.username == "darshan-test"

    fetched = await repo.get_by_github_id(99991)
    assert fetched is not None
    assert fetched.id == user.id

    updated = await repo.update(user.id, role="ADMIN")
    assert updated.role == "ADMIN"

    deleted = await repo.delete(user.id)
    assert deleted is True
    assert await repo.get(user.id) is None


@pytest.mark.asyncio
async def test_repository_and_pull_request_relationships(test_session: AsyncSession):
    repo_repo = RepositoryRepository(test_session)
    pr_repo = PullRequestRepository(test_session)

    repository = await repo_repo.create(
        github_repo_id=12345,
        name="codeguardian-test-repo",
        owner="test-org",
        url="https://github.com/test-org/codeguardian-test-repo",
        default_branch="main",
        language="python",
    )
    assert repository.id is not None

    pr = await pr_repo.create(
        github_pr_id=54321,
        repository_id=repository.id,
        number=42,
        title="feat: secure sql queries",
        author="dev-user",
        source_branch="feat/sql",
        target_branch="main",
        commit_sha="abcdef1234567890",
        status="OPEN",
    )
    assert pr.id is not None
    assert pr.repository_id == repository.id

    # Test relationship loader
    pr_with_repo = await pr_repo.get_with_repository(pr.id)
    assert pr_with_repo is not None
    assert pr_with_repo.repository.name == "codeguardian-test-repo"


@pytest.mark.asyncio
async def test_review_job_and_run_lifecycle(test_session: AsyncSession):
    repo_repo = RepositoryRepository(test_session)
    pr_repo = PullRequestRepository(test_session)
    job_repo = ReviewJobRepository(test_session)
    run_repo = ReviewRunRepository(test_session)

    repository = await repo_repo.create(
        github_repo_id=98765, name="api-service", owner="acme", url="https://github.com/acme/api", default_branch="main"
    )
    pr = await pr_repo.create(
        github_pr_id=11111,
        repository_id=repository.id,
        number=1,
        title="initial pr",
        author="alice",
        source_branch="feat/init",
        target_branch="main",
        commit_sha="sha123",
    )

    job = await job_repo.create(pull_request_id=pr.id, status="QUEUED")
    assert job.status == "QUEUED"

    running_job = await job_repo.mark_running(job.id)
    assert running_job.status == "RUNNING"
    assert running_job.started_at is not None

    run = await run_repo.create(
        review_job_id=job.id,
        configuration={"scanners": ["semgrep", "bandit"]},
        status="RUNNING",
        risk_score=75.0,
        risk_grade="D",
        summary="Found 1 critical issue",
    )
    assert run.id is not None

    completed_job = await job_repo.mark_completed(job.id)
    assert completed_job.status == "COMPLETED"
    assert completed_job.completed_at is not None


@pytest.mark.asyncio
async def test_finding_and_evidence_graph(test_session: AsyncSession):
    repo_repo = RepositoryRepository(test_session)
    pr_repo = PullRequestRepository(test_session)
    job_repo = ReviewJobRepository(test_session)
    run_repo = ReviewRunRepository(test_session)
    finding_repo = FindingRepository(test_session)
    evidence_repo = FindingEvidenceRepository(test_session)

    repo = await repo_repo.create(github_repo_id=1, name="r", owner="o", url="u", default_branch="main")
    pr = await pr_repo.create(github_pr_id=2, repository_id=repo.id, number=1, title="t", author="a", source_branch="s", target_branch="m", commit_sha="c")
    job = await job_repo.create(pull_request_id=pr.id)
    run = await run_repo.create(review_job_id=job.id, configuration={})

    finding = await finding_repo.create(
        review_run_id=run.id,
        fingerprint="fp1234567890",
        category="SECURITY",
        severity="CRITICAL",
        confidence=0.99,
        file_path="app/auth.py",
        line_start=10,
        line_end=12,
        title="SQL Injection",
        description="Raw query concatenation",
    )

    ev1 = await evidence_repo.create(
        finding_id=finding.id,
        source="SCANNER",
        tool="bandit",
        rule_id="B608",
        raw_message="Possible SQLi",
        metadata_payload={"confidence": "HIGH"},
    )
    ev2 = await evidence_repo.create(
        finding_id=finding.id,
        source="AGENT",
        tool="security_agent",
        rule_id="CWE-89",
        raw_message="Confirmed unescaped parameter",
        metadata_payload={"cvss": 9.8},
    )

    finding_with_ev = await finding_repo.get_with_evidence(finding.id)
    assert finding_with_ev is not None
    assert len(finding_with_ev.evidence) == 2

    counts = await finding_repo.get_severity_counts(run.id)
    assert counts.get("CRITICAL") == 1


@pytest.mark.asyncio
async def test_policy_and_chunks(test_session: AsyncSession):
    policy_repo = PolicyRepository(test_session)
    chunk_repo = PolicyChunkRepository(test_session)

    policy = await policy_repo.create(
        name="Crypto Policy",
        category="SECURITY_BASELINE",
        version="1.0.0",
        source="policies/security/crypto.md",
        active=True,
    )

    await chunk_repo.create(
        policy_id=policy.id,
        chunk_index=0,
        content="Never use MD5 or SHA1 for password hashing.",
        embedding_reference="ref_chunk_0",
    )
    await chunk_repo.create(
        policy_id=policy.id,
        chunk_index=1,
        content="Use Argon2id or bcrypt with cost factor >= 12.",
        embedding_reference="ref_chunk_1",
    )

    policy_with_chunks = await policy_repo.get_with_chunks(policy.id)
    assert policy_with_chunks is not None
    assert len(policy_with_chunks.chunks) == 2

    chunks = await chunk_repo.list_by_policy(policy.id)
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1


@pytest.mark.asyncio
async def test_remediation_and_fix_pr(test_session: AsyncSession):
    repo_repo = RepositoryRepository(test_session)
    pr_repo = PullRequestRepository(test_session)
    job_repo = ReviewJobRepository(test_session)
    run_repo = ReviewRunRepository(test_session)
    finding_repo = FindingRepository(test_session)
    remediation_repo = RemediationRepository(test_session)
    fix_pr_repo = FixPRRepository(test_session)

    repo = await repo_repo.create(github_repo_id=10, name="r", owner="o", url="u", default_branch="main")
    pr = await pr_repo.create(github_pr_id=20, repository_id=repo.id, number=1, title="t", author="a", source_branch="s", target_branch="m", commit_sha="c")
    job = await job_repo.create(pull_request_id=pr.id)
    run = await run_repo.create(review_job_id=job.id, configuration={})
    finding = await finding_repo.create(
        review_run_id=run.id, fingerprint="fp", category="SECURITY", severity="HIGH", confidence=1.0, file_path="x.py", title="t", description="d"
    )

    remediation = await remediation_repo.create(
        finding_id=finding.id,
        patch="--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-bad\n+good",
        status="VALIDATING",
        validation_result={},
    )
    assert remediation.status == "VALIDATING"

    validated = await remediation_repo.mark_validated(
        remediation.id, validation_result={"syntax": "PASSED", "tests": "PASSED"}
    )
    assert validated.status == "VALIDATED"

    fix_pr = await fix_pr_repo.create(
        remediation_attempt_id=remediation.id,
        github_pr_id=999,
        number=102,
        url="https://github.com/o/r/pull/102",
        status="OPEN",
    )
    assert fix_pr.id is not None

    remediation_with_pr = await remediation_repo.get_with_fix_pr(remediation.id)
    assert remediation_with_pr.fix_pr is not None
    assert remediation_with_pr.fix_pr.number == 102


@pytest.mark.asyncio
async def test_audit_log_tracking(test_session: AsyncSession):
    audit_repo = AuditRepository(test_session)

    entry = await audit_repo.record(
        actor="tanishq",
        action="TRIGGER_REVIEW",
        resource_type="PULL_REQUEST",
        resource_id="pr_123",
        metadata_payload={"branch": "feat/ai"},
    )
    assert entry.id is not None
    assert entry.action == "TRIGGER_REVIEW"

    logs = await audit_repo.list_by_resource("PULL_REQUEST", "pr_123")
    assert len(logs) == 1
    assert logs[0].actor == "tanishq"


@pytest.mark.asyncio
async def test_seed_database_execution(test_session: AsyncSession):
    from app.database.seed import seed_database
    await seed_database(test_session)

    user_repo = UserRepository(test_session)
    users = await user_repo.list()
    assert len(users) == 4

    repo_repo = RepositoryRepository(test_session)
    repos = await repo_repo.list()
    assert len(repos) == 1
    assert repos[0].name == "ecommerce-backend"

    pr_repo = PullRequestRepository(test_session)
    prs = await pr_repo.list()
    assert len(prs) == 1
    assert prs[0].number == 101

    finding_repo = FindingRepository(test_session)
    findings = await finding_repo.list()
    assert len(findings) == 2
