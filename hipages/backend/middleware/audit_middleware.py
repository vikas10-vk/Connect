import os
import re
import traceback
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from db.session import AsyncSessionLocal

# ── JWT decode (lightweight — reads Authorization header, no DB hit) ─
# Supports both PyJWT and python-jose (whichever your project uses)
try:
    import jwt as _jwt
    def _decode(token: str, secret: str, algo: str) -> dict:
        return _jwt.decode(token, secret, algorithms=[algo])
except ImportError:
    try:
        from jose import jwt as _jose
        def _decode(token: str, secret: str, algo: str) -> dict:
            return _jose.decode(token, secret, algorithms=[algo])
    except ImportError:
        def _decode(token: str, secret: str, algo: str) -> dict:
            raise RuntimeError("No JWT library found")

SECRET_KEY = os.getenv("SECRET_KEY", os.getenv("JWT_SECRET", ""))
ALGORITHM  = os.getenv("JWT_ALGORITHM", "HS256")

# ── Config ─────────────────────────────────────────────────────────
MUTATING_METHODS = {"POST", "PATCH", "PUT", "DELETE"}

SKIP_PATHS = {
    "/health", "/health/db",
    "/docs", "/openapi.json", "/redoc",
    "/sentry-debug",
}

# Extract entity_type and entity_id from URL path
# Order matters — more specific patterns first
ENTITY_PATTERNS = [
    (re.compile(r"/api/v1/jobs/([^/]+)/photos"),    "job_photo"),
    (re.compile(r"/api/v1/jobs/([^/]+)/review"),    "review"),
    (re.compile(r"/api/v1/jobs/([^/]+)/status"),    "job"),
    (re.compile(r"/api/v1/jobs/([^/]+)"),           "job"),
    (re.compile(r"/api/v1/quotes/([^/]+)"),         "quote"),
    (re.compile(r"/api/v1/leads/([^/]+)"),          "lead"),
    (re.compile(r"/api/v1/tradies/([^/]+)"),        "tradie"),
    (re.compile(r"/api/v1/reviews/([^/]+)"),        "review"),
    (re.compile(r"/api/v1/auth/"),                  "auth"),
    (re.compile(r"/api/v1/uploads/"),               "upload"),
    (re.compile(r"/api/v1/payments/"),              "payment"),
]

# Non-UUID path segments that should not be treated as entity IDs
NOT_AN_ID = {
    "my-jobs", "profile", "me", "history", "stats",
    "onboarding", "dashboard", "submit", "public",
    "inquiry", "competition", "confirm",
}


def _extract_actor(auth_header: str) -> tuple[str | None, str | None]:
    """Return (user_id, role) from Bearer token. Never raises."""
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, None
    try:
        payload = _decode(auth_header[7:], SECRET_KEY, ALGORITHM)
        return payload.get("sub"), payload.get("role")
    except Exception:
        return None, None


def _extract_entity(path: str) -> tuple[str | None, str | None]:
    """Return (entity_type, entity_id) from URL path."""
    for pattern, entity_type in ENTITY_PATTERNS:
        m = pattern.search(path)
        if m:
            entity_id = m.group(1) if m.lastindex and m.lastindex >= 1 else None
            if entity_id in NOT_AN_ID:
                entity_id = None
            return entity_type, entity_id
    return None, None


def _get_client_ip(request: Request) -> str:
    """Respects X-Forwarded-For for Nginx / Railway proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Middleware ──────────────────────────────────────────────────────

class AuditMiddleware(BaseHTTPMiddleware):
    """
    Auto-logs every mutating HTTP request that returns 2xx.
    Uses the shared AsyncSessionLocal pool — no extra connections.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        method = request.method
        path   = request.url.path

        # Fast path — skip reads and ignored routes
        if method not in MUTATING_METHODS or path in SKIP_PATHS:
            return await call_next(request)

        # Process the actual request first — always
        response = await call_next(request)

        # Only log successful mutations
        if response.status_code < 200 or response.status_code >= 300:
            return response

        # Fire-and-forget — never let audit failure crash the request
        try:
            await self._write(request, method, path, response.status_code)
        except Exception:
            print("[AUDIT] Write failed:")
            traceback.print_exc()

        return response

    async def _write(self, request: Request, method: str, path: str, status_code: int):
        from models.audit_event import AuditEvent

        actor_id, actor_role = _extract_actor(
            request.headers.get("authorization", "")
        )
        entity_type, entity_id = _extract_entity(path)

        async with AsyncSessionLocal() as session:
            session.add(AuditEvent(
                entity_type = entity_type,
                entity_id   = entity_id,
                actor_id    = actor_id,
                actor_role  = actor_role or "anonymous",
                action      = method,
                path        = path,
                status_code = status_code,
                ip_address  = _get_client_ip(request),
                user_agent  = request.headers.get("user-agent", "")[:500],
                created_at  = datetime.utcnow(),
            ))
            await session.commit()