"""Async SQLAlchemy engine, sessions, health checks, and initialization."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .base import Base
from .config import settings

logger = logging.getLogger("railro.database")

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout,
    pool_recycle=settings.database_pool_recycle,
)

AsyncSessionLocal = async_sessionmaker[AsyncSession](
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


async def check_database_connection() -> None:
    """Execute a lightweight query or raise the underlying connection error."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (OperationalError, DBAPIError, OSError):
        logger.exception("Database health query failed")
        raise
    except SQLAlchemyError:
        logger.exception("Unexpected SQLAlchemy database health failure")
        raise


async def init_db() -> None:
    """Import application models and create all missing tables."""
    # Importing registers the model on the shared Base metadata before create_all.
    from modules.eway_bill import models as eway_bill_models  # noqa: F401
    from modules.vehicles import models as vehicle_models  # noqa: F401

    logger.info("Initializing database tables")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    except (OperationalError, DBAPIError, OSError):
        logger.exception("Database table initialization failed")
        raise
    except SQLAlchemyError:
        logger.exception("Unexpected SQLAlchemy table initialization failure")
        raise
    logger.info("Database tables initialized")


async def get_db() -> AsyncIterator[AsyncSession]:
    """Provide one async database session to a FastAPI request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except HTTPException:
            raise
        except (OperationalError, DBAPIError, OSError) as exc:
            await session.rollback()
            logger.exception("Database request failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service is unavailable",
            ) from exc
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.exception("Database query failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database operation failed",
            ) from exc


async def close_database() -> None:
    """Close all pooled database connections."""
    await engine.dispose()
    logger.info("Database connection pool closed")
