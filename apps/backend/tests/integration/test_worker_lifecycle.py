import json
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config.settings import settings
from app.github.service import GitHubWebhookService
from app.models.audit import AuditLog
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob, ReviewRun
from app.schemas.queue import ReviewJobPayload
from app.workers.queue import MemoryReviewQueue
from app.workers.review_worker import ReviewWorker
from tests.unit.test_webhook_security import compute_test_signature, create_sample_pr_payload


@pytest.mark.asyncio
async def test_e2e_webhook_to_worker_success(async_client: AsyncClient, test_db):
    """
    Phase 4 End-to-End Acceptance Test:
      1. Webhook receives GitHub PR event.
      2. ReviewJob created in DB (QUEUED) and enqueued to queue broker.
      3. Background ReviewWorker dequeues the job.
      4. ReviewJob transitions QUEUED -> RUNNING -> COMPLETED.
      5. ReviewRun record is updated with status SUCCESS.
      6. AuditLog records the full lifecycle.
      7. Queue is properly acknowledged (ACK).
    """
    queue = MemoryReviewQueue()
    pr_number = 401
    head_sha = "aabbccddeeff00112233445566778899aabbccdd"
    delivery_id = "worker-e2e-deliv-001"

    payload_dict = create_sample_pr_payload(
        action="opened",
        pr_number=pr_number,
        repo_name="worker-target-repo",
        repo_owner="acme-corp",
        head_sha=head_sha,
    )
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    signature = compute_test_signature(payload_bytes, settings.GITHUB_WEBHOOK_SECRET)

    # 1. Process webhook using our queue
    async with test_db() as session:
        webhook_service = GitHubWebhookService(session=session, queue=queue)
        response = await webhook_service.process_webhook(
            raw_body=payload_bytes,
            signature_header=signature,
            event_type="pull_request",
            delivery_id=delivery_id,
        )
        assert response.status == "enqueued"
        job_id = response.job_id
        assert job_id is not None
        await session.commit()

    # 2. Verify queue received the job
    metrics = await queue.get_metrics()
    assert metrics.pending_jobs == 1
    assert metrics.processing_jobs == 0

    # 3. Instantiate and execute the ReviewWorker
    worker = ReviewWorker(
        queue=queue,
        session_factory=test_db,
        max_retries=3,
    )

    success = await worker.run_once(timeout=1)
    assert success is True

    # 4. Verify database state transitions to COMPLETED
    async with test_db() as session:
        job_res = await session.execute(select(ReviewJob).where(ReviewJob.id == job_id))
        job = job_res.scalars().first()
        assert job is not None
        assert job.status == "COMPLETED"
        assert job.started_at is not None
        assert job.completed_at is not None

        run_res = await session.execute(
            select(ReviewRun).where(ReviewRun.review_job_id == job_id)
        )
        run = run_res.scalars().first()
        assert run is not None
        assert run.status == "SUCCESS"
        assert run.completed_at is not None
        assert run.duration_ms is not None

        # Verify audit logs
        audit_res = await session.execute(
            select(AuditLog).where(
                AuditLog.resource_type == "review_job", AuditLog.resource_id == job_id
            )
        )
        actions = [a.action for a in audit_res.scalars().all()]
        assert "REVIEW_JOB_ENQUEUED" in actions
        assert "REVIEW_JOB_STARTED" in actions
        assert "REVIEW_JOB_COMPLETED" in actions

    # 5. Verify queue is acknowledged and empty
    final_metrics = await queue.get_metrics()
    assert final_metrics.pending_jobs == 0
    assert final_metrics.processing_jobs == 0
    assert final_metrics.dlq_jobs == 0


@pytest.mark.asyncio
async def test_worker_transient_failure_and_retry(test_db):
    """
    Verifies that when a transient failure occurs during review execution:
      1. Job status transitions to RETRYING in the database.
      2. Retry count is incremented.
      3. Job is re-enqueued to the pending queue with backoff.
    """
    queue = MemoryReviewQueue()

    # 1. Create Repository, PR, and ReviewJob in DB
    async with test_db() as session:
        repo = Repository(
            github_repo_id=77777,
            name="retry-repo",
            owner="acme",
            url="https://github.com/acme/retry-repo",
        )
        session.add(repo)
        await session.flush()

        pr = PullRequest(
            github_pr_id=88888,
            repository_id=repo.id,
            number=402,
            title="feat: test retries",
            author="dev",
            source_branch="feat/test",
            target_branch="main",
            commit_sha="1234567890abcdef",
            status="OPEN",
        )
        session.add(pr)
        await session.flush()

        job = ReviewJob(pull_request_id=pr.id, status="QUEUED")
        session.add(job)
        await session.commit()
        job_id = job.id

    # 2. Enqueue the job payload
    payload = ReviewJobPayload(
        job_id=job_id,
        pull_request_id=pr.id,
        repo_name="retry-repo",
        repo_owner="acme",
        pr_number=402,
        commit_sha="1234567890abcdef",
        retry_count=0,
    )
    await queue.enqueue_review(payload)

    # 3. Define execution handler that fails transiently
    async def failing_handler(p, s):
        raise TimeoutError("Simulated scanner subprocess timeout")

    worker = ReviewWorker(
        queue=queue,
        session_factory=test_db,
        max_retries=3,
        retry_backoff_seconds=0.01,
        execution_handler=failing_handler,
    )

    success = await worker.run_once(timeout=1)
    assert success is False

    # 4. Verify DB state is RETRYING
    async with test_db() as session:
        job_res = await session.execute(select(ReviewJob).where(ReviewJob.id == job_id))
        job = job_res.scalars().first()
        assert job.status == "RETRYING"
        assert job.retry_count == 1
        assert "timeout" in job.error_message.lower()

    # 5. Verify queue has re-enqueued the job for retry
    metrics = await queue.get_metrics()
    assert metrics.pending_jobs == 1
    assert metrics.processing_jobs == 0
    assert metrics.dlq_jobs == 0


@pytest.mark.asyncio
async def test_worker_exhausted_retries_routes_to_dlq(test_db):
    """
    Verifies that when maximum retries are exceeded:
      1. Job status transitions to FAILED in the database.
      2. ReviewRun status is marked FAILED.
      3. Job is permanently routed to Dead-Letter Queue (DLQ).
    """
    queue = MemoryReviewQueue()

    # 1. Create DB records
    async with test_db() as session:
        repo = Repository(
            github_repo_id=99991,
            name="dlq-repo",
            owner="acme",
            url="https://github.com/acme/dlq-repo",
        )
        session.add(repo)
        await session.flush()

        pr = PullRequest(
            github_pr_id=99992,
            repository_id=repo.id,
            number=403,
            title="feat: test dlq",
            author="dev",
            source_branch="feat/dlq",
            target_branch="main",
            commit_sha="9999999999999999",
            status="OPEN",
        )
        session.add(pr)
        await session.flush()

        job = ReviewJob(pull_request_id=pr.id, status="QUEUED")
        session.add(job)
        await session.commit()
        job_id = job.id

    # 2. Enqueue payload that is already on retry attempt 2 (max_retries = 3)
    payload = ReviewJobPayload(
        job_id=job_id,
        pull_request_id=pr.id,
        repo_name="dlq-repo",
        repo_owner="acme",
        pr_number=403,
        commit_sha="9999999999999999",
        retry_count=2,
    )
    await queue.enqueue_review(payload)

    # 3. Failing execution handler
    async def permanent_failure_handler(p, s):
        raise ValueError("Unrecoverable AST parser crash on malformed file")

    worker = ReviewWorker(
        queue=queue,
        session_factory=test_db,
        max_retries=3,
        execution_handler=permanent_failure_handler,
    )

    success = await worker.run_once(timeout=1)
    assert success is False

    # 4. Verify DB status is FAILED
    async with test_db() as session:
        job_res = await session.execute(select(ReviewJob).where(ReviewJob.id == job_id))
        job = job_res.scalars().first()
        assert job.status == "FAILED"
        assert job.retry_count == 3
        assert "unrecoverable" in job.error_message.lower()

        run_res = await session.execute(
            select(ReviewRun).where(ReviewRun.review_job_id == job_id)
        )
        run = run_res.scalars().first()
        assert run.status == "FAILED"

    # 5. Verify Dead-Letter Queue contains the failed job
    metrics = await queue.get_metrics()
    assert metrics.pending_jobs == 0
    assert metrics.processing_jobs == 0
    assert metrics.dlq_jobs == 1
