# =============================================================================
# middleware/request_id.py — Request ID injection
# Tradie Platform
# =============================================================================
#
# Assigns a unique ID to every request.
# This ID flows through:
#   nginx logs → FastAPI logs → Celery task logs → error responses
#
# When a user reports a problem, they can share the request_id from the
# error response and you can find the exact request in logs within seconds.
#
# Add to main.py:
#   from middleware.request_id import RequestIDMiddleware
#   app.add_middleware(RequestIDMiddleware)
# =============================================================================

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Use client-provided ID (from nginx or mobile app) or generate one.
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Store on request.state — available in any handler, middleware,
        # dependency, and exception handler that has access to Request.
        request.state.request_id = request_id

        response = await call_next(request)

        # Return the ID in response headers so the client/frontend can log it.
        response.headers["X-Request-ID"] = request_id

        return response
