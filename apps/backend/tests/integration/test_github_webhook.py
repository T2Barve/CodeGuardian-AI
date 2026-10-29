import json
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config.settings import settings
from app.models.audit import AuditLog
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob
from tests.unit.test_webhook_security import compute_test_signature, create_sample_pr_payload


@pytest.mark.asyncio
async def test_webhook_creates_database_records(async_client: AsyncClient, test_db):
    """
    Integration Acceptance Test:
    Verifies that ingesting a valid GitHub PR webhook successfully persists:
      1. Repository record
      2. PullRequest record with head SHA and branches
      3. ReviewJob record with status 'QUEUED'
      4. AuditLog compliance event
    """
    repo_name = "guardian-demo"
    repo_owner = "octocat"
    pr_number = 301
    head_sha = "d1e2f3a4b5c6789012345678901234567890abcd"
    delivery_id = "integration-deliv-001"

    payload_dict = create_sample_pr_payload(
        action="opened",
        pr_number=pr_number,
        repo_name=repo_name,
        repo_owner=repo_owner,
        head_sha=head_sha,
        head_ref="feature/sql-security",
        base_ref="main",
    )
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    signature = compute_test_signature(payload_bytes, settings.GITHUB_WEBHOOK_SECRET)

    response = await async_client.post(
        "/api/v1/github/webhook",
        content=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": delivery_id,
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "enqueued"
    job_id = data["job_id"]
    assert job_id is not None

    # Inspect the database records via test_db session
    async with test_db() as session:
        # 1. Verify Repository
        repo_result = await session.execute(
            select(Repository).where(Repository.name == repo_name, Repository.owner == repo_owner)
        )
        repo = repo_result.scalars().first()
        assert repo is not None
        assert repo.github_repo_id == payload_dict["repository"]["id"]
        assert repo.url == payload_dict["repository"]["html_url"]

        # 2. Verify PullRequest
        pr_result = await session.execute(
            select(PullRequest).where(
                PullRequest.repository_id == repo.id, PullRequest.number == pr_number
            )
        )
        pr = pr_result.scalars().first()
        assert pr is not None
        assert pr.commit_sha == head_sha
        assert pr.source_branch == "feature/sql-security"
        assert pr.target_branch == "main"
        assert pr.status == "OPEN"

        # 3. Verify ReviewJob
        job_result = await session.execute(select(ReviewJob).where(ReviewJob.id == job_id))
        job = job_result.scalars().first()
        assert job is not None
        assert job.pull_request_id == pr.id
        assert job.status == "QUEUED"
        assert job.queued_at is not None

        # 4. Verify AuditLog
        audit_result = await session.execute(
            select(AuditLog).where(
                AuditLog.resource_type == "review_job", AuditLog.resource_id == job_id
            )
        )
        audit = audit_result.scalars().first()
        assert audit is not None
        assert audit.action == "REVIEW_JOB_ENQUEUED"
        assert audit.metadata_payload["delivery_id"] == delivery_id
        assert audit.metadata_payload["commit_sha"] == head_sha


@pytest.mark.asyncio
async def test_webhook_synchronize_updates_commit_sha_and_creates_new_job(
    async_client: AsyncClient, test_db
):
    """
    Verifies that when developers push additional commits to an existing PR,
    the PR record updates to the newest commit SHA and a fresh ReviewJob is enqueued.
    """
    repo_name = "guardian-demo"
    repo_owner = "octocat"
    pr_number = 302
    initial_sha = "1111111111111111111111111111111111111111"
    updated_sha = "2222222222222222222222222222222222222222"

    # Step 1: Ingest opened event
    payload1 = create_sample_pr_payload(
        action="opened",
        pr_number=pr_number,
        repo_name=repo_name,
        repo_owner=repo_owner,
        head_sha=initial_sha,
    )
    bytes1 = json.dumps(payload1).encode("utf-8")
    sig1 = compute_test_signature(bytes1, settings.GITHUB_WEBHOOK_SECRET)
    resp1 = await async_client.post(
        "/api/v1/github/webhook",
        content=bytes1,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "sync-test-deliv-001",
            "X-Hub-Signature-256": sig1,
        },
    )
    assert resp1.status_code == 202
    job1_id = resp1.json()["job_id"]

    # Step 2: Ingest synchronize event with new commit SHA
    payload2 = create_sample_pr_payload(
        action="synchronize",
        pr_number=pr_number,
        repo_name=repo_name,
        repo_owner=repo_owner,
        head_sha=updated_sha,
    )
    bytes2 = json.dumps(payload2).encode("utf-8")
    sig2 = compute_test_signature(bytes2, settings.GITHUB_WEBHOOK_SECRET)
    resp2 = await async_client.post(
        "/api/v1/github/webhook",
        content=bytes2,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "sync-test-deliv-002",
            "X-Hub-Signature-256": sig2,
        },
    )
    assert resp2.status_code == 202
    job2_id = resp2.json()["job_id"]
    assert job1_id != job2_id

    # Verify database state
    async with test_db() as session:
        pr_result = await session.execute(
            select(PullRequest).where(PullRequest.number == pr_number)
        )
        pr = pr_result.scalars().first()
        assert pr is not None
        # PR commit_sha must have updated to the newest commit
        assert pr.commit_sha == updated_sha

        # Verify two review jobs exist for this PR
        jobs_result = await session.execute(
            select(ReviewJob).where(ReviewJob.pull_request_id == pr.id)
        )
        jobs = jobs_result.scalars().all()
        assert len(jobs) == 2
        job_ids = {j.id for j in jobs}
        assert job1_id in job_ids
        assert job2_id in job_ids


@pytest.mark.asyncio
async def test_webhook_closed_action_updates_pr_status_without_job(
    async_client: AsyncClient, test_db
):
    """
    Verifies that a 'closed' PR event updates the PullRequest status to 'CLOSED'
    and does NOT create a ReviewJob.
    """
    repo_name = "guardian-demo"
    repo_owner = "octocat"
    pr_number = 303
    head_sha = "3333333333333333333333333333333333333333"

    # Step 1: Open PR
    p_open = create_sample_pr_payload(
        action="opened",
        pr_number=pr_number,
        repo_name=repo_name,
        repo_owner=repo_owner,
        head_sha=head_sha,
    )
    b_open = json.dumps(p_open).encode("utf-8")
    sig_open = compute_test_signature(b_open, settings.GITHUB_WEBHOOK_SECRET)
    await async_client.post(
        "/api/v1/github/webhook",
        content=b_open,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "close-test-deliv-001",
            "X-Hub-Signature-256": sig_open,
        },
    )

    # Step 2: Close PR
    p_closed = create_sample_pr_payload(
        action="closed",
        pr_number=pr_number,
        repo_name=repo_name,
        repo_owner=repo_owner,
        head_sha=head_sha,
    )
    b_closed = json.dumps(p_closed).encode("utf-8")
    sig_closed = compute_test_signature(b_closed, settings.GITHUB_WEBHOOK_SECRET)
    resp = await async_client.post(
        "/api/v1/github/webhook",
        content=b_closed,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "close-test-deliv-002",
            "X-Hub-Signature-256": sig_closed,
        },
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "ignored"
    assert resp.json()["job_id"] is None

    # Verify DB: PR status is now CLOSED and only 1 ReviewJob exists (from opened)
    async with test_db() as session:
        pr_result = await session.execute(
            select(PullRequest).where(PullRequest.number == pr_number)
        )
        pr = pr_result.scalars().first()
        assert pr.status == "CLOSED"

        jobs_result = await session.execute(
            select(ReviewJob).where(ReviewJob.pull_request_id == pr.id)
        )
        jobs = jobs_result.scalars().all()
        assert len(jobs) == 1
