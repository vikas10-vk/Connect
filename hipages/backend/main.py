from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from db.session import check_database_health
from exceptions import register_exception_handlers
from middleware.audit_middleware import AuditMiddleware
from middleware.rate_limit import RateLimitMiddleware
from middleware.request_id import RequestIDMiddleware
from middleware.security_headers import SecurityHeadersMiddleware

# ── All existing router imports — UNCHANGED ──────────────────────────────────
from routers.auth import router as auth_router
from routers.tradies import router as tradies_router
from routers.categories import router as categories_router
from routers.jobs import router as jobs_router
from routers.leads import router as leads_router
from routers.quotes import router as quotes_router
from routers.reviews import router as reviews_router
from routers.websocket import router as ws_router
from routers.payments import router as payments_router
from routers.uploads import router as uploads_router
from routers.assets import router as assets_router
from routers.compliance import router as compliance_router
from routers.licence_guard import router as licence_guard_router
from routers.swms import router as swms_router
from routers.earnings import router as earnings_router
from routers.preferences import router as preferences_router
from routers.ai_chat import router as ai_chat_router
from routers.suburbs import router as suburbs_router
from routers.job_assignments import router as job_assignments_router

logger = logging.getLogger(__name__)

IS_PRODUCTION = os.getenv("ENVIRONMENT", "development") == "production"

# =============================================================================
# Sentry
# =============================================================================

SENTRY_DSN = os.getenv("SENTRY_BACKEND_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("ENVIRONMENT", "development"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        profiles_sample_rate=0.1,
        integrations=[FastApiIntegration(), SqlalchemyIntegration(), CeleryIntegration()],
        send_default_pii=False,
    )
    logger.info(f"Sentry initialised — environment: {os.getenv('ENVIRONMENT')}")
else:
    logger.warning("SENTRY_BACKEND_DSN not set — Sentry disabled")


# =============================================================================
# Lifespan — startup checks
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Tradie Platform API...")

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    app.state.redis_client = aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
        max_connections=20,
    )

    try:
        await check_database_health()
        logger.info("✓ Database connection verified")
    except Exception as e:
        logger.critical(f"✗ Database unreachable — refusing to start: {e}")
        sys.exit(1)

    try:
        await app.state.redis_client.ping()
        logger.info("✓ Redis connection verified")
    except Exception as e:
        logger.critical(f"✗ Redis unreachable — refusing to start: {e}")
        sys.exit(1)

    logger.info("✓ All startup checks passed — accepting traffic")

    yield

    logger.info("Shutting down...")

    try:
        await app.state.redis_client.aclose()
        logger.info("✓ Redis connection closed")
    except Exception as e:
        logger.warning(f"Shutdown — Redis close skipped: {e}")

    try:
        from db.session import engine
        await engine.dispose()
        logger.info("✓ Database engine disposed")
    except Exception as e:
        logger.warning(f"Shutdown — Engine dispose skipped: {e}")


# =============================================================================
# App
# =============================================================================

app = FastAPI(
    title="Tradie Platform API",
    version="1.0.0",
    default_response_class=ORJSONResponse,
    docs_url="/docs" if not IS_PRODUCTION else None,
    redoc_url=None,
    openapi_url="/openapi.json" if not IS_PRODUCTION else None,
    lifespan=lifespan,
)

register_exception_handlers(app)

# =============================================================================
# Middleware stack
# Registration order: innermost first, outermost last.
# Execution order on request: outermost first (reversed from registration).
# =============================================================================

# 4. Innermost
app.add_middleware(SecurityHeadersMiddleware)

# 3. Rate limiting
app.add_middleware(RateLimitMiddleware)

# 2. Audit logging
app.add_middleware(AuditMiddleware)

# 1. CORS — only in development.
#
# FIX: In production, nginx handles CORS via conf.d/api.conf.
# If FastAPI CORSMiddleware also ran in production, every response would have
# two Access-Control-Allow-Origin headers — browsers reject this entirely.
#
# In development (no nginx), FastAPI handles CORS so localhost:3000 works.
#
if not IS_PRODUCTION:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Idempotency-Key"],
        expose_headers=["X-Request-ID", "X-Response-Time"],
    )

# 0. Outermost — must run first so everything else has request_id.
app.add_middleware(RequestIDMiddleware)

# =============================================================================
# Routers — all existing routes preserved
# =============================================================================

app.include_router(auth_router)
app.include_router(tradies_router)
app.include_router(categories_router)
app.include_router(jobs_router)
app.include_router(leads_router)
app.include_router(quotes_router)
app.include_router(reviews_router)
app.include_router(ws_router)
app.include_router(payments_router)
app.include_router(uploads_router)
app.include_router(assets_router)
app.include_router(compliance_router)
app.include_router(licence_guard_router)
app.include_router(swms_router)
app.include_router(earnings_router)
app.include_router(preferences_router)
app.include_router(ai_chat_router)
app.include_router(suburbs_router)
app.include_router(job_assignments_router)


# =============================================================================
# Health endpoints
# =============================================================================

@app.get("/health", include_in_schema=False)
async def health() -> ORJSONResponse:
    result: dict[str, Any] = {"status": "ok", "checks": {}}
    overall_ok = True

    try:
        await check_database_health()
        result["checks"]["database"] = "ok"
    except Exception as e:
        result["checks"]["database"] = "error"
        overall_ok = False
        logger.error(f"Health check — database failed: {e}")

    try:
        redis_client = getattr(app.state, "redis_client", None)
        if redis_client:
            await redis_client.ping()
            result["checks"]["redis"] = "ok"
        else:
            result["checks"]["redis"] = "not_initialised"
            overall_ok = False
    except Exception as e:
        result["checks"]["redis"] = "error"
        overall_ok = False
        logger.error(f"Health check — Redis failed: {e}")

    if not overall_ok:
        result["status"] = "degraded"
        return ORJSONResponse(status_code=503, content=result)

    return ORJSONResponse(status_code=200, content=result)


@app.get("/health/db", include_in_schema=False)
async def health_db() -> ORJSONResponse:
    try:
        await check_database_health()
        return ORJSONResponse({"status": "ok", "database": "connected"})
    except Exception as e:
        return ORJSONResponse(
            status_code=503,
            content={"status": "error", "database": str(e)},
        )

# NOTE: /sentry-debug removed — never expose a deliberate exception trigger in production.