from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.metrics.service import MetricsService
from app.schemas.metrics import (
    EvaluationMetricsSummaryResponse,
    PerformanceMetricsResponse,
    QueueThroughputResponse,
    TokenCostMetricsResponse,
)

router = APIRouter(prefix="/metrics", tags=["Performance & Evaluation Metrics"])
metrics_service = MetricsService()


@router.get(
    "/performance",
    response_model=PerformanceMetricsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get End-to-End Latency Benchmarks & SLA Compliance",
    description="Returns empirical latency metrics (p50, p90, p95, p99, average), stage breakdown, and 120s SLA compliance.",
)
async def get_performance_benchmarks(
    db: AsyncSession = Depends(get_db),
) -> PerformanceMetricsResponse:
    """Retrieves latency benchmarks and SLA evaluation."""
    return await metrics_service.get_performance_metrics(session=db)


@router.get(
    "/token-cost",
    response_model=TokenCostMetricsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Multi-Agent Token Consumption & USD Cost Economics",
    description="Returns detailed token accounting across specialist agents, model costs, and ROI versus manual human code review.",
)
async def get_token_cost_metrics(
    db: AsyncSession = Depends(get_db),
) -> TokenCostMetricsResponse:
    """Retrieves multi-agent token usage and USD cost metrics."""
    return await metrics_service.get_token_cost_metrics(session=db)


@router.get(
    "/throughput",
    response_model=QueueThroughputResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Queue Throughput & DLQ Operational Health",
    description="Returns review throughput rates (reviews/min, reviews/hr), worker efficiency, and Dead Letter Queue health.",
)
async def get_queue_throughput(
    db: AsyncSession = Depends(get_db),
) -> QueueThroughputResponse:
    """Retrieves queue throughput and resiliency telemetry."""
    return await metrics_service.get_queue_throughput_metrics(session=db)


@router.get(
    "/evaluation-summary",
    response_model=EvaluationMetricsSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Comprehensive Academic Dissertation Evaluation Summary",
    description="Consolidates latency, economic token cost, and throughput metrics for academic defense presentation.",
)
async def get_evaluation_summary(
    db: AsyncSession = Depends(get_db),
) -> EvaluationMetricsSummaryResponse:
    """Retrieves full evaluation summary for academic presentation."""
    return await metrics_service.get_evaluation_summary(session=db)
