# =============================================================================
# exceptions.py — Custom exceptions and global error handlers
# Tradie Platform
# =============================================================================
#
# WHY THIS FILE IS NEEDED:
# Without this, when something goes wrong FastAPI returns:
#   {"detail": "Internal Server Error"}  ← no request ID, no error code
# or worse, it leaks a full Python stack trace to the client.
#
# With this file, every error returns:
#   {
#     "error": {
#       "code":       "AUTH_001",
#       "message":    "Invalid credentials",
#       "request_id": "550e8400-..."    ← find this in your logs instantly
#     }
#   }
#
# HOW TO USE IN ROUTERS:
#   from exceptions import NotFoundError, PermissionDeniedError
#   raise NotFoundError("Job", job_id)
#   raise PermissionDeniedError("You do not own this job")
# =============================================================================

import logging
import os
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


# =============================================================================
# Error response builder
# =============================================================================

def _error_body(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    detail: Any = None,
) -> dict[str, Any]:
    request_id = getattr(request.state, "request_id", "unknown")

    body: dict[str, Any] = {
        "error": {
            "code": error_code,
            "message": message,
            "request_id": request_id,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    }

    # Only include detail in development — prevents leaking internals.
    is_dev = os.getenv("ENVIRONMENT", "development") in ("development", "dev")
    if detail is not None and is_dev:
        body["error"]["detail"] = detail

    return body


# =============================================================================
# Base exception
# =============================================================================

class TradieBaseException(Exception):
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: str | None = None,
        detail: Any = None,
        error_code: str | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.detail = detail
        if error_code:
            self.error_code = error_code
        super().__init__(self.message)


# =============================================================================
# Auth exceptions (401, 403)
# =============================================================================

class AuthenticationError(TradieBaseException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "AUTH_001"
    message = "Authentication required"


class InvalidCredentialsError(TradieBaseException):
    """Never say which of email/password was wrong."""
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "AUTH_002"
    message = "Invalid email or password"


class TokenExpiredError(TradieBaseException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "AUTH_003"
    message = "Token has expired"


class RefreshTokenError(TradieBaseException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "AUTH_004"
    message = "Invalid or expired refresh token"


class AccountLockedError(TradieBaseException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "AUTH_005"
    message = "Account temporarily locked due to too many failed attempts"

    def __init__(self, retry_after_seconds: int = 900) -> None:
        super().__init__()
        self.retry_after_seconds = retry_after_seconds


class PermissionDeniedError(TradieBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "AUTHZ_001"
    message = "You do not have permission to perform this action"


class UnverifiedAccountError(TradieBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "AUTHZ_002"
    message = "Please verify your email address before continuing"


class SuspendedAccountError(TradieBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "AUTHZ_003"
    message = "Your account has been suspended. Please contact support."


# =============================================================================
# Resource exceptions (404, 409)
# =============================================================================

class NotFoundError(TradieBaseException):
    """
    Use for both genuine 404 AND IDOR protection.
    When a user requests a resource they don't own, return 404 not 403
    — returning 403 tells the attacker the resource exists.
    """
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"
    message = "Resource not found"

    def __init__(self, resource: str, resource_id: Any = None) -> None:
        super().__init__(message=f"{resource} not found")
        self.resource = resource
        self.resource_id = resource_id


class ConflictError(TradieBaseException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"
    message = "Operation conflicts with existing data"


# =============================================================================
# Business rule exceptions (422)
# =============================================================================

class BusinessRuleError(TradieBaseException):
    """
    Request is syntactically valid but violates a business rule.
    E.g.: tradie bids on own job, cancelling an already-completed job.
    """
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "BUSINESS_RULE"
    message = "Request violates a business rule"


class BookingStateError(TradieBaseException):
    """Invalid state machine transition."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "BOOKING_STATE"
    message = "This action is not allowed in the current booking state"

    def __init__(self, current_state: str, attempted_action: str) -> None:
        super().__init__(
            message=f"Cannot '{attempted_action}' when job is in '{current_state}' state"
        )
        self.detail = {
            "current_state": current_state,
            "attempted_action": attempted_action,
        }


# =============================================================================
# Payment exceptions (402)
# =============================================================================

class PaymentError(TradieBaseException):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    error_code = "PAYMENT_ERROR"
    message = "Payment could not be processed"

    def __init__(self, message: str, stripe_code: str | None = None) -> None:
        super().__init__(message=message)
        if stripe_code:
            self.detail = {"stripe_code": stripe_code}


# =============================================================================
# Rate limit (429)
# =============================================================================

class RateLimitError(TradieBaseException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "RATE_LIMIT"
    message = "Too many requests. Please slow down."

    def __init__(self, retry_after_seconds: int = 60) -> None:
        super().__init__()
        self.retry_after_seconds = retry_after_seconds


# =============================================================================
# Global exception handlers
# =============================================================================

async def tradie_exception_handler(
    request: Request,
    exc: TradieBaseException,
) -> ORJSONResponse:
    log_extra = {
        "error_code": exc.error_code,
        "status_code": exc.status_code,
        "request_id": getattr(request.state, "request_id", "unknown"),
        "path": str(request.url),
    }

    if exc.status_code >= 500:
        logger.error(exc.message, extra=log_extra, exc_info=True)
    else:
        logger.warning(exc.message, extra=log_extra)

    response = ORJSONResponse(
        status_code=exc.status_code,
        content=_error_body(request, exc.status_code, exc.error_code, exc.message, getattr(exc, "detail", None)),
    )

    if isinstance(exc, AuthenticationError | TokenExpiredError | RefreshTokenError):
        response.headers["WWW-Authenticate"] = "Bearer"

    if isinstance(exc, AccountLockedError):
        response.headers["Retry-After"] = str(exc.retry_after_seconds)

    if isinstance(exc, RateLimitError):
        response.headers["Retry-After"] = str(exc.retry_after_seconds)

    return response


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> ORJSONResponse:
    codes = {
        400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN",
        404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 408: "TIMEOUT",
        422: "VALIDATION_ERROR", 429: "RATE_LIMIT",
        500: "INTERNAL_ERROR", 503: "SERVICE_UNAVAILABLE",
    }
    error_code = codes.get(exc.status_code, f"HTTP_{exc.status_code}")
    message = exc.detail if isinstance(exc.detail, str) else "An error occurred"

    if exc.status_code >= 500:
        logger.error(f"HTTP {exc.status_code}: {message}")

    return ORJSONResponse(
        status_code=exc.status_code,
        content=_error_body(request, exc.status_code, error_code, message),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> ORJSONResponse:
    # FIX: include_url=False is Pydantic v2 only.
    # Some edge-case exception types reaching this handler don't support it.
    # Defensive call: try with include_url=False first, fall back without it.
    try:
        raw_errors = exc.errors(include_url=False)
    except TypeError:
        raw_errors = exc.errors()

    errors = [
        {
            "field": " → ".join(str(loc) for loc in e["loc"]),
            "message": e["msg"],
            "type": e["type"],
        }
        for e in raw_errors
    ]

    logger.warning(
        "Request validation failed",
        extra={"request_id": getattr(request.state, "request_id", "unknown"), "errors": errors},
    )

    return ORJSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_body(
            request, 422, "VALIDATION_ERROR",
            "Request validation failed",
            detail={"errors": errors},
        ),
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> ORJSONResponse:
    """
    Catches everything not caught above.
    Logs the full stack trace internally — never sends it to the client.
    """
    logger.critical(
        "Unhandled exception",
        extra={
            "request_id": getattr(request.state, "request_id", "unknown"),
            "path": str(request.url),
            "error_type": type(exc).__name__,
        },
        exc_info=True,
    )

    return ORJSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body(
            request, 500, "INTERNAL_ERROR",
            "An unexpected error occurred. Our team has been notified.",
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Call this from main.py to register all handlers."""
    app.add_exception_handler(TradieBaseException, tradie_exception_handler)       # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)      # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler) # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)