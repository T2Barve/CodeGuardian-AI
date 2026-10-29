from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, StaticPool
from app.config.settings import settings
from app.models.base import Base


def get_engine_args(database_url: str) -> dict:
    """Returns engine arguments optimized for database dialect."""
    if "sqlite" in database_url:
        return {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool if ":memory:" in database_url else NullPool,
        }
    return {
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    }


def create_engine_instance(database_url: str | None = None) -> AsyncEngine:
    """Creates a configured AsyncEngine."""
    url = database_url or settings.DATABASE_URL
    return create_async_engine(url, **get_engine_args(url))


engine: AsyncEngine = create_engine_instance()

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db(target_engine: AsyncEngine | None = None) -> None:
    """Creates all database tables defined in metadata and ensures initial admin account exists."""
    eng = target_engine or engine
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Ensure column password_hash exists in SQLite if table was previously created without it
    try:
        from sqlalchemy import text
        async with eng.begin() as conn:
            await conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
    except Exception:
        pass

    # Ensure default admin account exists for out-of-the-box local testing
    try:
        from app.models.user import User
        from app.security.auth import hash_password
        from sqlalchemy import select

        async with async_session_maker() as session:
            stmt = select(User).where(User.username == "admin")
            res = await session.execute(stmt)
            admin = res.scalars().first()
            if not admin:
                admin_user = User(
                    username="admin",
                    email="admin@codeguardian.local",
                    password_hash=hash_password("CodeGuardian2026!"),
                    role="SECURITY_LEAD",
                    avatar_url="https://api.dicebear.com/7.x/identicon/svg?seed=admin",
                )
                session.add(admin_user)
                await session.commit()
    except Exception:
        pass


async def drop_db(target_engine: AsyncEngine | None = None) -> None:
    """Drops all database tables defined in metadata."""
    eng = target_engine or engine
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
