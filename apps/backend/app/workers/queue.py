import abc
import asyncio
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from app.config.settings import settings
from app.schemas.queue import QueueMetrics, ReviewJobPayload
from app.utils.logging import get_logger

logger = get_logger("codeguardian.queue")

QUEUE_REVIEWS_KEY = "queue:reviews"
QUEUE_PROCESSING_KEY = "queue:reviews:processing"
QUEUE_DLQ_KEY = "dlq:reviews"
DEDUP_PREFIX = "queue:reviews:dedup:"
DEDUP_TTL_SECONDS = 86400  # 24 hours


class ReviewQueueInterface(abc.ABC):
    """Abstract interface defining the contract for review job queue operations."""

    @abc.abstractmethod
    async def enqueue_review(self, payload: ReviewJobPayload) -> bool:
        """Enqueues a review job payload. Returns True if enqueued, False if duplicate."""
        pass

    @abc.abstractmethod
    async def dequeue_review(self, timeout: int = 2) -> Optional[ReviewJobPayload]:
        """Atomically dequeues a job from pending to processing. Returns None on timeout."""
        pass

    @abc.abstractmethod
    async def ack_review(self, payload: ReviewJobPayload) -> None:
        """Acknowledges successful processing and removes job from the in-flight processing queue."""
        pass

    @abc.abstractmethod
    async def nack_review(
        self,
        payload: ReviewJobPayload,
        error_message: str,
        max_retries: int = 3,
        backoff_seconds: float = 0.0,
    ) -> None:
        """
        Negative acknowledgement: increments retry count. If retries remain,
        re-enqueues the job; otherwise routes to the dead-letter queue (DLQ).
        """
        pass

    @abc.abstractmethod
    async def get_metrics(self) -> QueueMetrics:
        """Returns counts for pending, in-flight processing, and dead-letter queues."""
        pass

    @abc.abstractmethod
    async def ping(self) -> bool:
        """Pings the queue broker to test connectivity."""
        pass

    @abc.abstractmethod
    async def clear(self) -> None:
        """Flushes queue keys (primarily for testing)."""
        pass

    @abc.abstractmethod
    async def close(self) -> None:
        """Closes broker connection."""
        pass


class RedisReviewQueue(ReviewQueueInterface):
    """
    Production-grade Redis-backed queue implementation utilizing atomic
    list operations (BLMOVE/BRPOPLPUSH) for guaranteed delivery and DLQ routing.
    """

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self._client: Optional[Any] = None

    async def _get_client(self) -> Any:
        if self._client is None:
            import redis.asyncio as aioredis
            self._client = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=1.0,
            )
        return self._client

    async def ping(self) -> bool:
        try:
            client = await self._get_client()
            return await client.ping() is True
        except Exception as exc:
            logger.debug("Redis ping failed", extra={"error": str(exc)})
            return False

    async def enqueue_review(self, payload: ReviewJobPayload) -> bool:
        try:
            client = await self._get_client()
            dedup_key = f"{DEDUP_PREFIX}{payload.job_id}"

            # 1. Enforce idempotency: skip if already queued within TTL
            is_new = await client.set(dedup_key, "1", nx=True, ex=DEDUP_TTL_SECONDS)
            if not is_new:
                logger.warning(
                    "Duplicate review job enqueue rejected by Redis dedup",
                    extra={"job_id": payload.job_id},
                )
                return False

            # 2. Push to head of pending queue
            serialized = payload.model_dump_json()
            await client.lpush(QUEUE_REVIEWS_KEY, serialized)
            logger.info(
                "Review job enqueued to Redis",
                extra={
                    "job_id": payload.job_id,
                    "repo": f"{payload.repo_owner}/{payload.repo_name}",
                    "pr": payload.pr_number,
                    "commit": payload.commit_sha[:8],
                },
            )
            return True
        except Exception as exc:
            if settings.ENVIRONMENT != "production":
                logger.warning(
                    f"Redis broker unreachable at {self.redis_url}; safely falling back to in-memory ReviewQueue: {exc}",
                    extra={"job_id": payload.job_id},
                )
                mem_q = get_review_queue(force_memory=True)
                return await mem_q.enqueue_review(payload)
            else:
                from app.schemas.errors import ProblemDetailException
                from fastapi import status
                raise ProblemDetailException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    title="Review Queue Unavailable",
                    detail=f"Redis queue broker is currently unreachable: {str(exc)}",
                )

    async def dequeue_review(self, timeout: int = 2) -> Optional[ReviewJobPayload]:
        try:
            client = await self._get_client()
            raw_payload = None

            try:
                # BLMOVE queue:reviews queue:reviews:processing RIGHT LEFT timeout
                # Atomic delivery guarantee: job moved from pending to processing
                raw_payload = await client.blmove(
                    first_list=QUEUE_REVIEWS_KEY,
                    second_list=QUEUE_PROCESSING_KEY,
                    src="RIGHT",
                    dest="LEFT",
                    timeout=timeout,
                )
            except Exception:
                # Fallback for Redis < 6.2 compatibility
                try:
                    raw_payload = await client.brpoplpush(
                        source=QUEUE_REVIEWS_KEY,
                        destination=QUEUE_PROCESSING_KEY,
                        timeout=timeout,
                    )
                except Exception as exc:
                    logger.debug("Failed to dequeue from Redis", extra={"error": str(exc)})
                    raw_payload = None

            if not raw_payload:
                if settings.ENVIRONMENT != "production":
                    mem_q = get_review_queue(force_memory=True)
                    return await mem_q.dequeue_review(timeout=0)
                return None

            try:
                payload_dict = json.loads(raw_payload)
                return ReviewJobPayload.model_validate(payload_dict)
            except Exception as exc:
                logger.error("Malformed payload in queue", extra={"error": str(exc), "raw": raw_payload[:100]})
                return None
        except Exception as exc:
            if settings.ENVIRONMENT != "production":
                mem_q = get_review_queue(force_memory=True)
                return await mem_q.dequeue_review(timeout=timeout)
            logger.error("Redis dequeue error", extra={"error": str(exc)})
            return None

    async def ack_review(self, payload: ReviewJobPayload) -> None:
        try:
            client = await self._get_client()
            # Remove from processing list by finding element with matching job_id
            items = await client.lrange(QUEUE_PROCESSING_KEY, 0, -1)
            for item in items:
                try:
                    data = json.loads(item)
                    if data.get("job_id") == payload.job_id:
                        await client.lrem(QUEUE_PROCESSING_KEY, 1, item)
                        logger.debug("Acknowledged and cleared job from processing queue", extra={"job_id": payload.job_id})
                        break
                except Exception:
                    continue
        except Exception:
            if settings.ENVIRONMENT != "production":
                mem_q = get_review_queue(force_memory=True)
                await mem_q.ack_review(payload)

    async def nack_review(
        self,
        payload: ReviewJobPayload,
        error_message: str,
        max_retries: int = 3,
        backoff_seconds: float = 0.0,
    ) -> None:
        try:
            client = await self._get_client()
            # 1. Remove from processing queue
            await self.ack_review(payload)

            # 2. Update failure telemetry
            payload.retry_count += 1
            payload.last_error = error_message
            serialized = payload.model_dump_json()

            # 3. Check retry exhaustion
            if payload.retry_count < max_retries:
                if backoff_seconds > 0:
                    await asyncio.sleep(backoff_seconds)
                # Requeue to pending
                await client.rpush(QUEUE_REVIEWS_KEY, serialized)
                logger.warning(
                    "Job nacked and re-enqueued for retry",
                    extra={
                        "job_id": payload.job_id,
                        "retry_count": payload.retry_count,
                        "max_retries": max_retries,
                        "error": error_message,
                    },
                )
            else:
                # Route to Dead-Letter Queue
                await client.lpush(QUEUE_DLQ_KEY, serialized)
                logger.error(
                    "Job exhausted retries; routed to Dead-Letter Queue (DLQ)",
                    extra={
                        "job_id": payload.job_id,
                        "retries": payload.retry_count,
                        "dlq": QUEUE_DLQ_KEY,
                        "error": error_message,
                    },
                )
        except Exception:
            if settings.ENVIRONMENT != "production":
                mem_q = get_review_queue(force_memory=True)
                await mem_q.nack_review(
                    payload=payload,
                    error_message=error_message,
                    max_retries=max_retries,
                    backoff_seconds=backoff_seconds,
                )

    async def get_metrics(self) -> QueueMetrics:
        try:
            client = await self._get_client()
            pending = await client.llen(QUEUE_REVIEWS_KEY)
            processing = await client.llen(QUEUE_PROCESSING_KEY)
            dlq = await client.llen(QUEUE_DLQ_KEY)
            return QueueMetrics(
                pending_jobs=pending,
                processing_jobs=processing,
                dlq_jobs=dlq,
            )
        except Exception:
            if settings.ENVIRONMENT != "production":
                mem_q = get_review_queue(force_memory=True)
                return await mem_q.get_metrics()
            return QueueMetrics(pending_jobs=0, processing_jobs=0, dlq_jobs=0)

    async def clear(self) -> None:
        client = await self._get_client()
        await client.delete(QUEUE_REVIEWS_KEY, QUEUE_PROCESSING_KEY, QUEUE_DLQ_KEY)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


class MemoryReviewQueue(ReviewQueueInterface):
    """
    In-memory queue implementation mirroring Redis queue behavior with atomic
    move, acknowledgements, retries, and dead-letter routing for testing and standalone mode.
    """

    def __init__(self):
        self._pending: List[ReviewJobPayload] = []
        self._processing: Dict[str, ReviewJobPayload] = {}
        self._dlq: List[ReviewJobPayload] = []
        self._dedup: set[str] = set()
        self._lock = asyncio.Lock()

    async def ping(self) -> bool:
        return True

    async def enqueue_review(self, payload: ReviewJobPayload) -> bool:
        async with self._lock:
            if payload.job_id in self._dedup:
                logger.warning(
                    "Duplicate job rejected in memory queue", extra={"job_id": payload.job_id}
                )
                return False
            self._dedup.add(payload.job_id)
            self._pending.append(payload)
            logger.info("Enqueued job to memory queue", extra={"job_id": payload.job_id})
            return True

    async def dequeue_review(self, timeout: int = 2) -> Optional[ReviewJobPayload]:
        # Polling wait up to timeout
        step = 0.05
        elapsed = 0.0
        while elapsed <= timeout:
            async with self._lock:
                if self._pending:
                    job = self._pending.pop(0)
                    self._processing[job.job_id] = job
                    return job
            if timeout <= 0:
                break
            await asyncio.sleep(step)
            elapsed += step
        return None

    async def ack_review(self, payload: ReviewJobPayload) -> None:
        async with self._lock:
            self._processing.pop(payload.job_id, None)

    async def nack_review(
        self,
        payload: ReviewJobPayload,
        error_message: str,
        max_retries: int = 3,
        backoff_seconds: float = 0.0,
    ) -> None:
        async with self._lock:
            self._processing.pop(payload.job_id, None)
            payload.retry_count += 1
            payload.last_error = error_message

            if payload.retry_count < max_retries:
                if backoff_seconds > 0:
                    await asyncio.sleep(backoff_seconds)
                self._pending.append(payload)
                logger.warning(
                    "Job nacked and re-enqueued for retry (memory)",
                    extra={"job_id": payload.job_id, "retry_count": payload.retry_count},
                )
            else:
                self._dlq.append(payload)
                logger.error(
                    "Job routed to dead-letter queue (memory)",
                    extra={"job_id": payload.job_id, "error": error_message},
                )

    async def get_metrics(self) -> QueueMetrics:
        async with self._lock:
            return QueueMetrics(
                pending_jobs=len(self._pending),
                processing_jobs=len(self._processing),
                dlq_jobs=len(self._dlq),
            )

    async def clear(self) -> None:
        async with self._lock:
            self._pending.clear()
            self._processing.clear()
            self._dlq.clear()
            self._dedup.clear()

    async def close(self) -> None:
        await self.clear()


# Shared singleton memory queue instance for fallback & testing
_shared_memory_queue: Optional[MemoryReviewQueue] = None


def get_review_queue(
    redis_url: Optional[str] = None,
    force_memory: bool = False,
) -> ReviewQueueInterface:
    """
    Factory function returning a configured ReviewQueue.
    Uses MemoryReviewQueue when force_memory is True, otherwise provides RedisReviewQueue.
    """
    global _shared_memory_queue
    if force_memory:
        if _shared_memory_queue is None:
            _shared_memory_queue = MemoryReviewQueue()
        return _shared_memory_queue

    return RedisReviewQueue(redis_url=redis_url or settings.REDIS_URL)
