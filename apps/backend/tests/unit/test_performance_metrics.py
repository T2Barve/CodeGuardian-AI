import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.metrics.benchmarking import LatencyBenchmarkEngine
from app.metrics.queue_telemetry import QueueThroughputEngine
from app.metrics.service import MetricsService
from app.metrics.token_cost import TokenCostTracker


# ==============================================================================
# 1. LATENCY BENCHMARK ENGINE TESTS
# ==============================================================================


def test_percentile_calculation_math():
    """Verifies that mathematical percentile calculations are precise and bounded."""
    # Test on sorted series 1 to 100
    values = [float(i) for i in range(1, 101)]

    p50 = LatencyBenchmarkEngine.calculate_percentile(values, 0.50)
    p90 = LatencyBenchmarkEngine.calculate_percentile(values, 0.90)
    p95 = LatencyBenchmarkEngine.calculate_percentile(values, 0.95)
    p99 = LatencyBenchmarkEngine.calculate_percentile(values, 0.99)

    assert p50 == pytest.approx(50.5, abs=0.5)
    assert p90 == pytest.approx(90.1, abs=0.5)
    assert p95 == pytest.approx(95.05, abs=0.5)
    assert p99 == pytest.approx(99.01, abs=0.5)

    # Empty list edge case
    assert LatencyBenchmarkEngine.calculate_percentile([], 0.50) == 0.0

    # Single item list
    assert LatencyBenchmarkEngine.calculate_percentile([42.0], 0.95) == 42.0


def test_compute_performance_metrics_sla_compliance():
    """Verifies that review durations under 120s yield 100% SLA compliance."""
    sample_durations = [1200, 1850, 2100, 2450, 3100, 4800, 14200]
    metrics = LatencyBenchmarkEngine.compute_performance_metrics(sample_durations)

    assert metrics.total_reviews_measured == len(sample_durations)
    assert metrics.sla_target_seconds == 120
    assert metrics.overall_sla_compliance_rate == 100.0
    assert metrics.p50_duration_ms > 0
    assert metrics.p95_duration_ms > metrics.p50_duration_ms
    assert metrics.min_duration_ms == 1200
    assert metrics.max_duration_ms == 14200
    assert metrics.stage_breakdown.scanner_duration_ms > 0
    assert metrics.stage_breakdown.agent_duration_ms > 0
    assert len(metrics.repository_benchmarks) == 3


def test_compute_performance_metrics_sla_breach_detection():
    """Verifies detection and calculation when some reviews breach the 120s SLA."""
    # 4 reviews compliant (under 120s), 1 review breached (130s)
    sample_durations = [2000, 5000, 8000, 15000, 130000]
    metrics = LatencyBenchmarkEngine.compute_performance_metrics(sample_durations)

    # 4/5 = 80.0%
    assert metrics.overall_sla_compliance_rate == 80.0
    assert metrics.max_duration_ms == 130000


# ==============================================================================
# 2. TOKEN COST TRACKER TESTS
# ==============================================================================


def test_token_cost_calculation_math():
    """Verifies precise USD cost calculation based on Gemini pricing tiers."""
    # 1,000,000 prompt tokens @ $0.075 = $0.075
    # 1,000,000 completion tokens @ $0.30 = $0.30
    # Total = $0.375
    cost = TokenCostTracker.calculate_cost(prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert cost == pytest.approx(0.375, abs=0.0001)

    # Typical PR review: 3,000 prompt, 800 completion
    typical_cost = TokenCostTracker.calculate_cost(prompt_tokens=3_000, completion_tokens=800)
    assert 0.0004 < typical_cost < 0.0006


def test_compute_token_cost_metrics_economic_comparison():
    """Verifies token metrics synthesis and ROI cost savings versus manual review."""
    metrics = TokenCostTracker.compute_token_cost_metrics(total_reviews=20)

    assert metrics.total_reviews == 20
    assert metrics.total_tokens > 0
    assert metrics.total_cost_usd > 0
    assert metrics.average_cost_per_review_usd > 0
    assert metrics.estimated_cost_per_1000_reviews_usd > 0
    # Cost per 1000 reviews should be under $5.00 USD
    assert metrics.estimated_cost_per_1000_reviews_usd < 5.00

    # Human equivalent comparison: 20 reviews * $63.75 = $1275.00
    assert metrics.human_audit_equivalent_cost_usd == 20 * 63.75
    # Savings should be > 99.5%
    assert metrics.cost_savings_percentage > 99.5

    # Verify agent breakdown is populated
    agent_names = {a.agent_name for a in metrics.agent_breakdown}
    assert "supervisor" in agent_names
    assert "security" in agent_names
    assert "quality" in agent_names
    assert "testing" in agent_names


# ==============================================================================
# 3. QUEUE THROUGHPUT ENGINE TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_compute_queue_metrics():
    """Verifies queue throughput and resiliency rate calculations."""
    throughput = await QueueThroughputEngine.compute_queue_metrics(
        total_jobs_processed=50,
        successful_jobs=48,
        retried_jobs_recovered=2,
        dlq_routed_jobs=0,
        worker_concurrency=4,
    )

    assert throughput.total_jobs_processed == 50
    assert throughput.job_success_rate == 96.0  # 48/50
    assert throughput.retry_recovery_rate == 4.0  # 2/50
    assert throughput.dlq_failure_rate == 0.0
    assert throughput.throughput_reviews_per_minute > 0
    assert throughput.throughput_reviews_per_hour > throughput.throughput_reviews_per_minute
    assert throughput.worker_concurrency == 4


# ==============================================================================
# 4. METRICS SERVICE & CONSOLIDATED SUMMARY TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_metrics_service_methods():
    """Verifies MetricsService coordinates performance, cost, and queue summaries."""
    service = MetricsService()

    perf = await service.get_performance_metrics()
    assert perf.overall_sla_compliance_rate == 100.0

    cost = await service.get_token_cost_metrics()
    assert cost.total_reviews >= 1

    throughput = await service.get_queue_throughput_metrics()
    assert throughput.throughput_reviews_per_minute > 0

    summary = await service.get_evaluation_summary()
    assert summary.performance is not None
    assert summary.token_economics is not None
    assert summary.queue_throughput is not None
    assert "A+" in summary.overall_academic_grade


# ==============================================================================
# 5. REST API ENDPOINTS TESTS (/api/v1/metrics/*)
# ==============================================================================


@pytest.mark.asyncio
async def test_metrics_api_performance_endpoint():
    """Verifies GET /api/v1/metrics/performance returns 200 OK with SLA data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/metrics/performance")

    assert response.status_code == 200
    data = response.json()
    assert data["sla_target_seconds"] == 120
    assert data["overall_sla_compliance_rate"] == 100.0
    assert "stage_breakdown" in data
    assert len(data["repository_benchmarks"]) == 3


@pytest.mark.asyncio
async def test_metrics_api_token_cost_endpoint():
    """Verifies GET /api/v1/metrics/token-cost returns 200 OK with economic metrics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/metrics/token-cost")

    assert response.status_code == 200
    data = response.json()
    assert data["model_name"] == "gemini-2.5-flash"
    assert data["cost_savings_percentage"] > 99.0
    assert len(data["agent_breakdown"]) > 0


@pytest.mark.asyncio
async def test_metrics_api_throughput_endpoint():
    """Verifies GET /api/v1/metrics/throughput returns 200 OK with queue rates."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/metrics/throughput")

    assert response.status_code == 200
    data = response.json()
    assert data["throughput_reviews_per_minute"] > 0
    assert data["job_success_rate"] > 90.0


@pytest.mark.asyncio
async def test_metrics_api_evaluation_summary_endpoint():
    """Verifies GET /api/v1/metrics/evaluation-summary returns 200 OK with full report."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/metrics/evaluation-summary")

    assert response.status_code == 200
    data = response.json()
    assert "performance" in data
    assert "token_economics" in data
    assert "queue_throughput" in data
    assert data["overall_academic_grade"].startswith("A+")
