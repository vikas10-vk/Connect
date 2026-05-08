# =============================================================================
# middleware/security_headers.py — Security response headers
# Tradie Platform
# =============================================================================
#
# Adds security headers to every response.
# nginx adds these in production — this middleware adds them as a backup so:
# - Development (no nginx) also has them
# - If nginx misconfiguration drops a header, it's still present
#
# Add to main.py:
#   from middleware.security_headers import SecurityHeadersMiddleware
#   app.add_middleware(SecurityHeadersMiddleware)
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
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

        # Remove headers that reveal server software.
        response.headers.pop("Server", None)
        response.headers.pop("X-Powered-By", None)

        return response