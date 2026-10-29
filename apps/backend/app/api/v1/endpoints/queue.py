from fastapi import APIRouter, status
from app.schemas.queue import QueueMetrics
from app.workers.queue import get_review_queue
from app.utils.logging import get_logger

logger = get_logger("codeguardian.api.queue")

router = APIRouter(prefix="/queue", tags=["Queue & Workers"])


@router.get(
    "/metrics",
    response_model=QueueMetrics,
    status_code=status.HTTP_200_OK,
    summary="Get Queue Telemetry Metrics",
    description="Returns current queue depth for pending review jobs, in-flight processing jobs, and dead-letter queue (DLQ).",
)
async def get_queue_metrics() -> QueueMetrics:
    """Retrieves operational telemetry for Redis job queues."""
    queue = get_review_queue()
    try:
        return await queue.get_metrics()
    except Exception as exc:
        logger.error("Failed to query queue metrics", extra={"error": str(exc)})
        # Return fallback zero metrics if broker is offline in dev
        return QueueMetrics(pending_jobs=0, processing_jobs=0, dlq_jobs=0)
