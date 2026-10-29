import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database.session import get_db
from app.github.security import clear_memory_delivery_store
from app.main import app
from app.models.base import Base


@pytest.fixture(scope="function")
async def test_db():
    """Provides an isolated in-memory SQLite database session factory for API testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    yield session_maker

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_db):
    """Provides a fresh isolated database session for testing."""
    async with test_db() as session:
        yield session


@pytest.fixture(scope="function")
async def async_client(test_db):
    """Provides an asynchronous HTTP test client bound to the FastAPI app with test DB override."""
    async def override_get_db():
        async with test_db() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    clear_memory_delivery_store()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
    clear_memory_delivery_store()


@pytest.fixture(autouse=True)
def isolate_test_tokens(monkeypatch):
    """Ensures test suites always execute against safe mock tokens instead of calling live APIs."""
    from app.config.settings import settings
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://127.0.0.1:63799/0")

