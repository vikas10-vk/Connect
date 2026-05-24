# =============================================================================
# middleware/security_headers.py — Security response headers
# Tradie Platform
# =============================================================================
#
# FIX: Starlette 0.28+ removed .pop() from MutableHeaders.
# Replaced with explicit key existence check before deletion.
# Affects: "Server" and "X-Powered-By" header removal.
# =============================================================================

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)

        # Prevent MIME type sniffing.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")

        # Clickjacking protection.
        response.headers.setdefault("X-Frame-Options", "DENY")

        # Don't leak referrer across origins.
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )

        # Remove headers that reveal server software.
        # FIX: MutableHeaders.pop() was removed in Starlette 0.28+.
        # Use explicit membership check + del instead.
        if "server" in response.headers:
            del response.headers["server"]
        if "x-powered-by" in response.headers:
            del response.headers["x-powered-by"]

        return response