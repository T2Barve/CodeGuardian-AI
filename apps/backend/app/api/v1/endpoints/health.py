from datetime import datetime, timezone
from fastapi import APIRouter, status
from sqlalchemy import text
from app.config.settings import settings
from app.database.session import engine
from app.schemas.health import HealthResponse, ReadinessResponse
from app.workers.queue import get_review_queue

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness Probe",
    description="Returns service liveness status and version metadata."
)
async def get_health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        timestamp=datetime.now(timezone.utc),
        environment=settings.ENVIRONMENT,
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness Probe",
    description="Validates downstream dependencies (PostgreSQL and Redis)."
)
async def get_readiness() -> ReadinessResponse:
    db_status = "disconnected"
    redis_status = "disconnected"

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception:
        db_status = "disconnected"

    try:
        queue = get_review_queue()
        is_redis_ok = await queue.ping()
        redis_status = "connected" if is_redis_ok else "disconnected"
    except Exception:
        redis_status = "disconnected"

    is_ready = db_status == "connected" or settings.ENVIRONMENT == "development"

    return ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        database=db_status,
        redis=redis_status,
        error=None if is_ready else "Database connection unavailable",
    )
