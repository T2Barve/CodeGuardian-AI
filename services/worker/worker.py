import asyncio
import signal
import sys
from typing import Optional

from app.config.settings import settings
from app.utils.logging import get_logger, setup_logging
from app.workers.queue import get_review_queue
from app.workers.review_worker import ReviewWorker

setup_logging()
logger = get_logger("codeguardian.worker")

worker_instance: Optional[ReviewWorker] = None


def handle_shutdown(signum, frame):
    global worker_instance
    logger.info(
        "Received termination signal, shutting down worker gracefully...",
        extra={"signal": signum},
    )
    if worker_instance:
        worker_instance.stop()


async def run_worker():
    global worker_instance
    logger.info(
        "Starting CodeGuardian AI Background Review Worker Daemon",
        extra={
            "environment": settings.ENVIRONMENT,
            "redis_url": settings.REDIS_URL,
            "version": settings.VERSION,
        },
    )

    queue = get_review_queue()
    worker_instance = ReviewWorker(queue=queue)

    # Register OS signals for graceful shutdown
    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: handle_shutdown(sig, None))
    else:
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info("Review worker initialized. Actively polling for review jobs...")

    try:
        await worker_instance.run_loop()
    finally:
        await queue.close()

    logger.info("CodeGuardian AI Review Worker stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(run_worker())
