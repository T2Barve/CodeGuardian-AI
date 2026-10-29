import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import async_session_maker, init_db
from app.models.user import User
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.policy import Policy, PolicyChunk
from app.models.review import ReviewJob, ReviewRun
from app.models.finding import Finding, FindingEvidence
from app.models.agent import AgentRun
from app.models.remediation import RemediationAttempt, FixPR
from app.models.audit import AuditLog
from app.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger("codeguardian.seed")


async def seed_database(session: AsyncSession) -> None:
    """Seeds initial demonstration and benchmark records into database."""
    await init_db()
    logger.info("Checking for existing seed data...")

    from sqlalchemy import select
    existing_user = (await session.execute(select(User).limit(1))).scalars().first()
    if existing_user:
        logger.info("Seed data already present in database. Skipping re-seeding.")
        return

    # 1. Seed Users (B.Tech Team Members)
    users_data = [
        User(github_id=1001, username="darshan", email="darshan@codeguardian.ai", role="DEVELOPER"),
        User(github_id=1002, username="tanishq", email="tanishq@codeguardian.ai", role="REVIEWER"),
        User(github_id=1003, username="mayur", email="mayur@codeguardian.ai", role="ADMIN"),
        User(github_id=1004, username="veer", email="veer@codeguardian.ai", role="ADMIN"),
    ]
    session.add_all(users_data)
    await session.flush()
    logger.info(f"Seeded {len(users_data)} team users.")

    # 2. Seed Benchmark Repository
    repo = Repository(
        github_repo_id=98765432,
        name="ecommerce-backend",
        owner="acme-corp",
        url="https://github.com/acme-corp/ecommerce-backend",
        default_branch="main",
        language="python",
        is_active=True,
    )
    session.add(repo)
    await session.flush()
    logger.info(f"Seeded repository: {repo.owner}/{repo.name}")

    # 3. Seed Pull Request
    pr = PullRequest(
        github_pr_id=12345678,
        repository_id=repo.id,
        number=101,
        title="feat: add user authentication and database queries",
        author="darshan",
        source_branch="feat/auth",
        target_branch="main",
        commit_sha="e7a4b2c1f90d8a6b4e3c2a1f0d9e8b7a6c5d4e3f",
        status="OPEN",
    )
    session.add(pr)
    await session.flush()
    logger.info(f"Seeded Pull Request #{pr.number}")

    # 4. Seed Engineering Policies for RAG
    sec_policy = Policy(
        name="SQL Injection & Database Access Standards",
        category="SECURITY_BASELINE",
        version="1.0.0",
        source="policies/security/db_security.md",
        active=True,
    )
    session.add(sec_policy)
    await session.flush()

    chunk1 = PolicyChunk(
        policy_id=sec_policy.id,
        chunk_index=0,
        content="All SQL queries touching relational storage must use ORM binding or text(:param) syntax. String formatting or f-strings inside raw SQL queries are strictly prohibited.",
        embedding_reference="chunk_sec_db_001",
        metadata_payload={"section": "2.1 Query Parameterization", "cwe": "CWE-89"},
    )
    session.add(chunk1)

    qual_policy = Policy(
        name="Code Quality & Complexity Standards",
        category="CODING_STANDARD",
        version="1.0.0",
        source="policies/coding-standards/maintainability.md",
        active=True,
    )
    session.add(qual_policy)
    await session.flush()

    chunk2 = PolicyChunk(
        policy_id=qual_policy.id,
        chunk_index=0,
        content="Functions must not exceed cyclomatic complexity of 15 or 50 lines in total length. Repeated business logic exceeding 20 lines must be extracted into reusable service components.",
        embedding_reference="chunk_qual_comp_001",
        metadata_payload={"section": "1.3 Complexity Limits", "max_cyclomatic": 15},
    )
    session.add(chunk2)
    logger.info("Seeded RAG policies and chunks.")

    # 5. Seed ReviewJob & ReviewRun
    job = ReviewJob(
        pull_request_id=pr.id,
        status="COMPLETED",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        retry_count=0,
    )
    session.add(job)
    await session.flush()

    run = ReviewRun(
        review_job_id=job.id,
        configuration={"scanners": ["semgrep", "bandit", "gitleaks", "eslint"]},
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        duration_ms=18450,
        status="SUCCESS",
        risk_score=68.5,
        risk_grade="C",
        summary="Review completed. Identified 1 CRITICAL SQL injection vulnerability and 1 HIGH code quality complexity violation.",
    )
    session.add(run)
    await session.flush()

    # 6. Seed Correlated Findings with Evidence
    finding1 = Finding(
        review_run_id=run.id,
        fingerprint="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        category="SECURITY",
        severity="CRITICAL",
        confidence=0.98,
        status="OPEN",
        file_path="services/auth/views.py",
        line_start=42,
        line_end=45,
        title="Raw SQL Query Concatenation (SQLi)",
        description="Untrusted user input formatted directly into raw SQL query without parameterized binding.",
        impact="Remote attacker could bypass login authentication or extract customer data.",
        recommendation="Use parameterized query with text(:username) parameter binding.",
        policy_reference="SEC-POL-01: SQL Injection & Database Access Standards",
    )
    session.add(finding1)
    await session.flush()

    ev1 = FindingEvidence(
        finding_id=finding1.id,
        source="SCANNER",
        tool="bandit",
        rule_id="B608",
        raw_message="Possible SQL injection vector through string-based query construction.",
        code_snippet="query = f\"SELECT * FROM users WHERE username = '{username}'\"",
        metadata_payload={"confidence": "HIGH", "severity": "MEDIUM"},
    )
    ev2 = FindingEvidence(
        finding_id=finding1.id,
        source="AGENT",
        tool="security_agent",
        rule_id="CWE-89",
        raw_message="Exploitable SQL injection confirmed in login endpoint. Direct input reaches database without ORM validation.",
        code_snippet="query = f\"SELECT * FROM users WHERE username = '{username}'\"",
        metadata_payload={"cvss_v3_score": 9.8, "exploitability": "HIGH"},
    )
    session.add_all([ev1, ev2])

    finding2 = Finding(
        review_run_id=run.id,
        fingerprint="7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b",
        category="QUALITY",
        severity="HIGH",
        confidence=0.92,
        status="OPEN",
        file_path="services/billing/calculator.py",
        line_start=12,
        line_end=85,
        title="Excessive Cyclomatic Complexity (Complexity=28)",
        description="Method calculate_invoice exceeds cyclomatic complexity limit of 15 (measured: 28) with deeply nested conditionals.",
        impact="High risk of logic bugs during edge-case payment handling and maintenance regressions.",
        recommendation="Refactor tax and discount calculation into separate strategy functions.",
        policy_reference="QUAL-POL-01: Code Quality & Complexity Standards",
    )
    session.add(finding2)
    await session.flush()

    # 7. Seed Agent Runs
    agent_sec = AgentRun(
        review_run_id=run.id,
        agent_name="security_agent",
        status="COMPLETED",
        duration_ms=4200,
        prompt_tokens=1850,
        completion_tokens=420,
        total_tokens=2270,
        estimated_cost=0.0045,
    )
    agent_qual = AgentRun(
        review_run_id=run.id,
        agent_name="quality_agent",
        status="COMPLETED",
        duration_ms=3800,
        prompt_tokens=1600,
        completion_tokens=380,
        total_tokens=1980,
        estimated_cost=0.0039,
    )
    session.add_all([agent_sec, agent_qual])

    # 8. Seed Remediation Attempt & Fix PR
    remediation = RemediationAttempt(
        finding_id=finding1.id,
        requested_by=users_data[0].id,
        patch="--- a/services/auth/views.py\n+++ b/services/auth/views.py\n@@ -42,3 +42,3 @@\n-query = f\"SELECT * FROM users WHERE username = '{username}'\"\n+query = select(User).where(User.username == username)",
        status="VALIDATED",
        validation_result={
            "syntax_check": "PASSED",
            "unit_tests": "PASSED (14/14 tests)",
            "scanner_check": "PASSED (B608 eliminated, 0 new findings)",
            "regression_tests": "PASSED",
        },
    )
    session.add(remediation)
    await session.flush()

    fix_pr = FixPR(
        remediation_attempt_id=remediation.id,
        github_pr_id=87654321,
        number=102,
        url="https://github.com/acme-corp/ecommerce-backend/pull/102",
        status="OPEN",
    )
    session.add(fix_pr)

    # 9. Seed Audit Log
    audit = AuditLog(
        actor="system",
        action="SEED_DATABASE",
        resource_type="SYSTEM",
        resource_id="init",
        metadata_payload={"environment": "development", "entities_seeded": 9},
    )
    session.add(audit)

    await session.commit()
    logger.info("Database seeding successfully completed!")


async def main():
    await init_db()
    async with async_session_maker() as session:
        await seed_database(session)


if __name__ == "__main__":
    asyncio.run(main())
