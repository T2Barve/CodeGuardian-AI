import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_health(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "api-gateway"
    assert "version" in data


@pytest.mark.asyncio
async def test_api_v1_health(async_client: AsyncClient):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["environment"] == "development"
    assert "version" in data
    assert "timestamp" in data

    # Verify telemetry headers
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time" in response.headers


@pytest.mark.asyncio
async def test_api_v1_readiness(async_client: AsyncClient):
    response = await async_client.get("/api/v1/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "database" in data
    assert "redis" in data
