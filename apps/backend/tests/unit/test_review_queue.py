import pytest
from httpx import AsyncClient

from app.schemas.queue import QueueMetrics, ReviewJobPayload
from app.workers.queue import MemoryReviewQueue, get_review_queue


def create_sample_job_payload(job_id: str = "job-uuid-001", retry_count: int = 0) -> ReviewJobPayload:
    return ReviewJobPayload(
        job_id=job_id,
        pull_request_id="pr-uuid-001",
        repo_name="ecommerce-backend",
        repo_owner="acme-corp",
        pr_number=101,
        commit_sha="a1b2c3d4e5f67890",
        action="opened",
        retry_count=retry_count,
    )


@pytest.mark.asyncio
async def test_queue_payload_serialization():
    """Verifies ReviewJobPayload validation and JSON serialization."""
    payload = create_sample_job_payload()
    json_str = payload.model_dump_json()
    assert "job-uuid-001" in json_str
    assert "ecommerce-backend" in json_str

    deserialized = ReviewJobPayload.model_validate_json(json_str)
    assert deserialized.job_id == payload.job_id
    assert deserialized.pr_number == 101
    assert deserialized.retry_count == 0


@pytest.mark.asyncio
async def test_memory_queue_enqueue_and_deduplication():
    """Verifies that duplicate job IDs within TTL are rejected by the queue."""
    queue = MemoryReviewQueue()
    payload = create_sample_job_payload("job-dedup-1")

    # First enqueue: True
    assert await queue.enqueue_review(payload) is True

    # Duplicate enqueue: False
    assert await queue.enqueue_review(payload) is False

    metrics = await queue.get_metrics()
    assert metrics.pending_jobs == 1
    assert metrics.processing_jobs == 0
    assert metrics.dlq_jobs == 0


@pytest.mark.asyncio
async def test_memory_queue_atomic_dequeue_and_ack():
    """Verifies atomic transfer from pending to in-flight processing, then ACK."""
    queue = MemoryReviewQueue()
    payload = create_sample_job_payload("job-ack-1")
    await queue.enqueue_review(payload)

    # Dequeue
    dequeued = await queue.dequeue_review(timeout=0)
    assert dequeued is not None
    assert dequeued.job_id == "job-ack-1"

    # In-flight processing state
    metrics = await queue.get_metrics()
    assert metrics.pending_jobs == 0
    assert metrics.processing_jobs == 1

    # ACK
    await queue.ack_review(dequeued)
    metrics_after_ack = await queue.get_metrics()
    assert metrics_after_ack.processing_jobs == 0


@pytest.mark.asyncio
async def test_memory_queue_nack_and_retry_backoff():
    """Verifies that NACK re-enqueues the job when retries are under the limit."""
    queue = MemoryReviewQueue()
    payload = create_sample_job_payload("job-retry-1", retry_count=0)
    await queue.enqueue_review(payload)

    dequeued = await queue.dequeue_review(timeout=0)
    assert dequeued is not None

    # NACK with max_retries = 3
    await queue.nack_review(dequeued, error_message="Timeout during scan", max_retries=3)

    metrics = await queue.get_metrics()
    assert metrics.processing_jobs == 0
    assert metrics.pending_jobs == 1
    assert metrics.dlq_jobs == 0

    # Next dequeued job has updated retry_count
    retry_job = await queue.dequeue_review(timeout=0)
    assert retry_job is not None
    assert retry_job.retry_count == 1
    assert retry_job.last_error == "Timeout during scan"


@pytest.mark.asyncio
async def test_memory_queue_dead_letter_queue_routing():
    """Verifies that exceeding max retries routes the job to DLQ."""
    queue = MemoryReviewQueue()
    # Job that has already been retried 2 times
    payload = create_sample_job_payload("job-dlq-1", retry_count=2)
    await queue.enqueue_review(payload)

    dequeued = await queue.dequeue_review(timeout=0)
    assert dequeued is not None

    # NACK when retry_count reaches max_retries (3)
    await queue.nack_review(
        dequeued, error_message="Persistent syntax check failure", max_retries=3
    )

    metrics = await queue.get_metrics()
    assert metrics.pending_jobs == 0
    assert metrics.processing_jobs == 0
    assert metrics.dlq_jobs == 1


@pytest.mark.asyncio
async def test_queue_metrics_api_endpoint(async_client: AsyncClient):
    """Verifies GET /api/v1/queue/metrics returns 200 with QueueMetrics payload."""
    response = await async_client.get("/api/v1/queue/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "pending_jobs" in data
    assert "processing_jobs" in data
    assert "dlq_jobs" in data
    assert isinstance(data["pending_jobs"], int)
