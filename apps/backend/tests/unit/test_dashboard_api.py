import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.session import get_db
from app.main import app
from app.models.base import Base
from app.database.seed import seed_database


@pytest.fixture
async def test_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_dashboard_summary_and_seed(test_db_session: AsyncSession):
    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Seed database via API
        res_seed = await client.post("/api/v1/dashboard/seed")
        assert res_seed.status_code == 201
        assert res_seed.json()["status"] == "SUCCESS"

        # Check dashboard summary
        res = await client.get("/api/v1/dashboard/summary")
        assert res.status_code == 200
        data = res.json()
        assert data["total_repositories"] >= 1
        assert data["total_reviews"] >= 1
        assert data["critical_findings"] >= 1
        assert data["category_radar"]["security"] > 0
        assert len(data["recent_reviews"]) >= 1
        assert data["recent_reviews"][0]["repo_name"] == "ecommerce-backend"

        # Check repositories endpoint
        res_repos = await client.get("/api/v1/repositories")
        assert res_repos.status_code == 200
        repos = res_repos.json()
        assert len(repos) >= 1
        repo_id = repos[0]["id"]

        # Check single repo detail
        res_repo_detail = await client.get(f"/api/v1/repositories/{repo_id}")
        assert res_repo_detail.status_code == 200
        repo_detail = res_repo_detail.json()
        assert repo_detail["name"] == "ecommerce-backend"
        assert len(repo_detail["recent_pull_requests"]) >= 1

    app.dependency_overrides.clear()
