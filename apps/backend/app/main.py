import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.v1.api import api_router
from app.config.settings import settings
from app.schemas.errors import ProblemDetailException
from app.utils.logging import get_logger, setup_logging

# Configure structured logging
setup_logging()
logger = get_logger("codeguardian.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and graceful shutdown lifecycles."""
    logger.info(
        "Starting CodeGuardian AI API Gateway",
        extra={
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "api_prefix": settings.API_V1_PREFIX,
        },
    )
    # Ensure database schema is initialized
    from app.database.session import init_db
    try:
        await init_db()
    except Exception as e:
        logger.warning(f"Database schema init: {e}")

    # Launch background ReviewWorker to process enqueued review and analysis jobs
    import asyncio
    from app.workers.review_worker import ReviewWorker
    from app.workers.queue import get_review_queue

    worker_task = None
    worker = None
    try:
        queue = get_review_queue()
        worker = ReviewWorker(queue=queue)
        worker_task = asyncio.create_task(worker.run_loop())
        logger.info("Background ReviewWorker loop spawned successfully")
    except Exception as w_err:
        logger.warning(f"Background ReviewWorker startup notice: {w_err}")

    yield

    logger.info("Shutting down CodeGuardian AI API Gateway")
    if worker and worker_task:
        worker.stop()
        worker_task.cancel()
        try:
            await asyncio.wait_for(worker_task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Autonomous Multi-Agent Code Review & DevSecOps Platform API Gateway",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
)

# Security Middleware (OWASP Top 10 API Security Hardening)
from app.security.middleware import ContentLengthLimitMiddleware, SecurityHeadersMiddleware

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(ContentLengthLimitMiddleware)

# CORS Configuration
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Telemetry and Request ID Middleware
@app.middleware("http")
async def add_process_time_and_request_id(request: Request, call_next) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.perf_counter()

    response = await call_next(request)

    process_time = time.perf_counter() - start_time
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    return response


# RFC 7807 Problem Details Exception Handler
@app.exception_handler(ProblemDetailException)
async def problem_detail_exception_handler(request: Request, exc: ProblemDetailException) -> JSONResponse:
    content = {
        "type": exc.type_uri,
        "title": exc.title,
        "status": exc.status_code,
        "detail": exc.detail,
        "instance": exc.instance or request.url.path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers={"Content-Type": "application/problem+json"},
    )


# Top-level probe routes for standard container orchestrators
@app.get("/health", include_in_schema=False)
async def root_health():
    return {"status": "healthy", "service": "api-gateway", "version": settings.VERSION}


# Include versioned API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "title": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": f"{settings.API_V1_PREFIX}/docs",
        "health_url": f"{settings.API_V1_PREFIX}/health",
    }
