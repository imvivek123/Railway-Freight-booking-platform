"""RailRo FastAPI application entry point and infrastructure lifecycle."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from starlette.middleware.base import RequestResponseEndpoint

from core.config import settings
from core.database import (
    AsyncSessionLocal,
    check_database_connection,
    close_database,
    init_db,
)
from core.db_health import router as db_health_router
from modules.eway_bill import router as eway_bill_router
from modules.vehicles import router as vehicle_driver_router

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("railro.startup")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and close PostgreSQL and Redis application resources."""
    redis: Redis | None = None

    app.state.db_sessionmaker = AsyncSessionLocal
    app.state.redis = None

    logger.info("Validating database startup connection")
    try:
        await check_database_connection()
        logger.info("Database connected successfully")
        await init_db()
    except Exception:
        # Keep diagnostics and /db-health available while returning 503 for DB use.
        logger.exception("Database connection failed")

    if settings.redis_url:
        try:
            redis = Redis.from_url(settings.redis_url, decode_responses=False)
            await redis.ping()
            app.state.redis = redis
            logger.info("Redis connected")
        except Exception:
            logger.exception("Redis connection failed")
            if redis is not None:
                await redis.aclose()
                redis = None
    else:
        logger.warning("Redis not configured: REDIS_URL is missing")

    logger.info("Routers loaded")
    for route in app.routes:
        methods = ",".join(sorted(getattr(route, "methods", set()) or set()))
        logger.info("Route registered: %-7s %s", methods, route.path)
    logger.info("App started")

    try:
        yield
    finally:
        if redis is not None:
            await redis.aclose()
            logger.info("Redis connection closed")
        await close_database()
        logger.info("App stopped")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="RailRo modular-monolith API.",
    debug=settings.app_debug,
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    """Log request method, path, response status, and execution time."""
    started_at = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception:
        logger.exception("Unhandled exception while processing request")
        raise
    finally:
        elapsed_ms = (perf_counter() - started_at) * 1000
        logger.info(
            "HTTP method=%s path=%s status=%s execution_ms=%.2f",
            request.method,
            request.url.path,
            status_code,
            elapsed_ms,
        )


app.include_router(eway_bill_router)
app.include_router(vehicle_driver_router)
app.include_router(db_health_router)


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Return a lightweight application health response."""
    return {"status": "ok"}
