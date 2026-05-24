# =============================================================================
# middleware/rate_limit.py â€” Redis-based rate limiting
# Tradie Platform
# =============================================================================
#
# FIX APPLIED: request.state.user_id was always None inside middleware.
#
# WHY: FastAPI dependencies (get_current_user) run inside route handlers,
# AFTER middleware has already executed. So request.state.user_id was never
# set when this middleware ran â€” the per-user rate limiting never activated.
#
# FIX: Decode the JWT directly from the Authorization header inside this
# middleware. This is NOT authentication â€” it's purely to make the rate
# limit key user-specific. The route dependency still performs full auth.
#
# NOTE: We set verify_exp=False intentionally. We want to rate-limit by
# user_id even for expired tokens â€” otherwise an expired-token request
# gets the weaker IP-based limit instead of the user-specific one.
# Rejecting expired tokens is the auth dependency's job, not ours.
# =============================================================================

import logging
import os
import time
from collections.abc import Awaitable, Callable

from jose import jwt as _jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

RATE_LIMIT = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "100"))
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM  = os.getenv("ALGORITHM", "HS256")

# Paths that skip rate limiting entirely.
EXEMPT_PATHS = {
    "/health",
    "/health/db",
}


class RateLimitMiddleware(BaseHTTPMiddleware):

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:

        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        redis_client = getattr(request.app.state, "redis_client", None)
        if redis_client is None:
            logger.error("Rate limit check skipped â€” Redis unavailable")
            return await call_next(request)

        # â”€â”€ Extract user identity â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        #
        # We decode the JWT directly here because middleware runs before route
        # dependencies. request.state.user_id would always be None otherwise.
        #
        # This is NOT authentication â€” we do not reject expired tokens here.
        # We just want to know: is this request from a known user?
        # Authentication (including token expiry) is the route dependency's job.
        #
        user_id: str | None = None

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and SECRET_KEY:
            try:
                token   = auth_header[7:]
                payload = _jwt.decode(
                    token,
                    SECRET_KEY,
                    algorithms=[ALGORITHM],
                    options={
                        "verify_exp": False,   # Do not reject expired tokens here.
                        "verify_aud": False,   # No audience claim in our tokens.
                    },
                )
                user_id = payload.get("sub")
            except Exception:
                # Invalid token â€” fall through to IP-based limiting.
                # Authentication will reject it later in the route dependency.
                pass

        # â”€â”€ Build rate limit key â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if user_id:
            # Per-user: authenticated users are limited by their account,
            # not their IP. This prevents bypass via IP rotation.
            identifier = f"user:{user_id}"
        else:
            # Per-IP: unauthenticated requests (login, register, public endpoints).
            ip = request.headers.get("X-Real-IP") or (
                request.client.host if request.client else "unknown"
            )
            identifier = f"ip:{ip}"

        # â”€â”€ Sliding window counter â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        bucket    = int(time.time()) // 60
        redis_key = f"rate:{identifier}:{bucket}"

        try:
            async with redis_client.pipeline(transaction=True) as pipe:
                pipe.incr(redis_key)
                pipe.expire(redis_key, 120)   # 2-minute TTL covers current + previous window
                results = await pipe.execute()

            count = results[0]

            if count > RATE_LIMIT:
                logger.warning(
                    "Rate limit exceeded",
                    extra={
                        "identifier": identifier,
                        "count": count,
                        "limit": RATE_LIMIT,
                        "request_id": getattr(request.state, "request_id", "unknown"),
                        "path": request.url.path,
                    },
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT",
                            "message": "Too many requests. Please slow down.",
                            "request_id": getattr(request.state, "request_id", "unknown"),
                        }
                    },
                    headers={"Retry-After": "60"},
                )

        except Exception as e:
            # Redis error â€” fail open (don't block all traffic for a Redis blip).
            logger.error(f"Rate limit Redis error: {e}")

        return await call_next(request)
