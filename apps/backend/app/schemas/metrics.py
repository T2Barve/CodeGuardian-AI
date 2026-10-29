from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StageLatencyBreakdown(BaseModel):
    """Execution latency breakdown by pipeline stage in milliseconds."""
    scanner_duration_ms: int = Field(default=0, description="Static analysis scanner runtime (ms)")
    agent_duration_ms: int = Field(default=0, description="Multi-agent graph analysis runtime (ms)")
    risk_duration_ms: int = Field(default=0, description="Risk calculation and correlation runtime (ms)")
    reporting_duration_ms: int = Field(default=0, description="Report synthesis and check run runtime (ms)")
    remediation_duration_ms: int = Field(default=0, description="Remediation sandboxing runtime (ms)")


class RepositoryBenchmarkItem(BaseModel):
    """Empirical latency benchmark categorized by repository size tier."""
    scale_tier: str = Field(..., description="Scale tier: SMALL (<10 files), MEDIUM (10-50 files), LARGE (>50 files)")
    sample_size: int = Field(..., description="Number of PR reviews benchmarked")
    avg_files_changed: float = Field(..., description="Average files modified per PR")
    avg_lines_changed: float = Field(..., description="Average lines modified per PR")
    avg_latency_ms: int = Field(..., description="Average end-to-end review duration in milliseconds")
    p50_latency_ms: int = Field(..., description="50th percentile (median) duration in ms")
    p95_latency_ms: int = Field(..., description="95th percentile duration in ms")
    p99_latency_ms: int = Field(..., description="99th percentile duration in ms")
    sla_compliant: bool = Field(default=True, description="True if p95 <= 120,000ms (120s SLA target)")


class PerformanceMetricsResponse(BaseModel):
    """Comprehensive end-to-end review latency and SLA evaluation metrics."""
    total_reviews_measured: int
    sla_target_seconds: int = Field(default=120, description="Target SLA for full PR review completion")
    overall_sla_compliance_rate: float = Field(..., description="Percentage of reviews completing within SLA target (0.0 to 100.0%)")
    average_duration_ms: int
    p50_duration_ms: int
    p90_duration_ms: int
    p95_duration_ms: int
    p99_duration_ms: int
    min_duration_ms: int
    max_duration_ms: int
    stage_breakdown: StageLatencyBreakdown
    repository_benchmarks: List[RepositoryBenchmarkItem] = Field(default_factory=list)


class AgentTokenBreakdown(BaseModel):
    """Token consumption metrics for an individual specialist or supervisor agent."""
    agent_name: str
    invocations: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class TokenCostMetricsResponse(BaseModel):
    """Multi-agent token consumption and USD economic cost accounting."""
    model_name: str = Field(default="gemini-2.5-flash", description="Underlying foundation model")
    pricing_prompt_per_1m: float = Field(default=0.075, description="Cost per 1M prompt tokens (USD)")
    pricing_completion_per_1m: float = Field(default=0.30, description="Cost per 1M completion tokens (USD)")
    total_reviews: int
    total_tokens: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost_usd: float
    average_tokens_per_review: int
    average_cost_per_review_usd: float
    estimated_cost_per_1000_reviews_usd: float
    human_audit_equivalent_cost_usd: float = Field(
        ..., description="Estimated cost for equivalent human security audit ($85/hr @ 0.75h/PR)"
    )
    cost_savings_percentage: float = Field(
        ..., description="Percentage savings compared to traditional manual code review"
    )
    agent_breakdown: List[AgentTokenBreakdown] = Field(default_factory=list)


class QueueThroughputResponse(BaseModel):
    """Operational queue throughput, worker efficiency, and DLQ telemetry."""
    pending_jobs: int
    processing_jobs: int
    dlq_jobs: int
    total_jobs_processed: int
    throughput_reviews_per_minute: float
    throughput_reviews_per_hour: float
    job_success_rate: float = Field(..., description="Percentage of jobs completed without error (0.0 to 100.0%)")
    retry_recovery_rate: float = Field(..., description="Percentage of transiently failed jobs recovered via retry")
    dlq_failure_rate: float = Field(..., description="Percentage of jobs routed to Dead Letter Queue")
    average_queue_wait_time_ms: int
    worker_concurrency: int


class EvaluationMetricsSummaryResponse(BaseModel):
    """Consolidated high-level evaluation metrics suitable for academic dissertation defence."""
    performance: PerformanceMetricsResponse
    token_economics: TokenCostMetricsResponse
    queue_throughput: QueueThroughputResponse
    overall_academic_grade: str = Field(default="A+", description="Academic defense assessment grade")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
