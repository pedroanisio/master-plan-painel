"""Unified error-envelope contract for the API.

Every error the API emits — request validation, authentication, authorization,
domain conflicts, not-found, and unexpected server faults — is rendered as one
JSON shape::

    {
      "error": {
        "code": "duplicate_name",       # stable, machine-readable
        "message": "a project named 'alpha' already exists",
        "request_id": "8f4c…",          # also echoed in the X-Request-ID header
        "details": [                      # optional; field-level validation info
          {"field": "name", "message": "String should have at least 1 character"}
        ]
      }
    }

Clients branch on ``error.code`` (stable) rather than string-matching
``message`` (human-facing, may change). ``request_id`` correlates a client-side
failure with the server log line for the same request.

⚠ ARCHITECTURAL CONTRACT (PALS's LAW): the catch-all 500 handler treats the
raised exception as untrusted — its text is logged server-side but **never**
returned to the client, so internal paths, secrets, or stack traces cannot
leak through an error body.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from master_plan.api.repository import DuplicateColorError, DuplicateNameError
from master_plan.api.user_repository import DuplicateUserError

__all__ = [
    "ErrorCode",
    "FieldError",
    "ErrorBody",
    "ErrorEnvelope",
    "AppError",
    "install_error_handlers",
]

_log = logging.getLogger("master_plan.api")


class ErrorCode:
    """Stable, machine-readable error codes returned in ``error.code``.

    These are part of the API contract: clients may switch on them, so a code
    must never change meaning once shipped (add a new one instead).
    """

    VALIDATION_ERROR = "validation_error"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    DUPLICATE_NAME = "duplicate_name"
    DUPLICATE_COLOR = "duplicate_color"
    DUPLICATE_USER = "duplicate_user"
    BAD_REQUEST = "bad_request"
    HTTP_ERROR = "http_error"
    INTERNAL_ERROR = "internal_error"


# HTTP status -> error code for generic ``HTTPException``s raised by routes that
# do not carry a more specific domain code.
_STATUS_CODE_MAP: dict[int, str] = {
    400: ErrorCode.BAD_REQUEST,
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    409: ErrorCode.CONFLICT,
    422: ErrorCode.VALIDATION_ERROR,
}


class FieldError(BaseModel):
    """A single field-level validation problem."""

    field: str = Field(..., description="Dotted path to the offending field.")
    message: str = Field(..., description="Human-readable reason it is invalid.")


class ErrorBody(BaseModel):
    """The inner error object of an :class:`ErrorEnvelope`."""

    code: str = Field(..., description="Stable, machine-readable error code.")
    message: str = Field(..., description="Human-readable summary of the failure.")
    request_id: str = Field(..., description="Correlates with the X-Request-ID header.")
    details: list[FieldError] | None = Field(
        default=None, description="Field-level problems, when applicable."
    )


class ErrorEnvelope(BaseModel):
    """The single JSON shape every error response uses."""

    error: ErrorBody


class AppError(Exception):
    """Application error that renders directly to an :class:`ErrorEnvelope`.

    Raise this (or let a mapped domain exception propagate) instead of building
    an ``HTTPException`` when a route wants a specific ``code`` and/or
    field-level ``details``.
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        details: list[FieldError] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def _new_request_id() -> str:
    return uuid.uuid4().hex


def _field_errors(exc: ValidationError | RequestValidationError) -> list[FieldError]:
    """Flatten pydantic/FastAPI validation errors into :class:`FieldError`s.

    The leading location segment (``body``/``query``/``path`` for FastAPI, or the
    model name for a bare pydantic error) is dropped so ``field`` is the dotted
    path the client actually sent.
    """
    out: list[FieldError] = []
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", ())]
        field = ".".join(loc[1:]) if len(loc) > 1 else (loc[0] if loc else "")
        out.append(FieldError(field=field or "(root)", message=err.get("msg", "invalid")))
    return out


def _render(
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    *,
    details: list[FieldError] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    envelope = ErrorEnvelope(
        error=ErrorBody(
            code=code, message=message, request_id=request_id, details=details
        )
    )
    response_headers = {"X-Request-ID": request_id}
    if headers:
        response_headers.update(headers)
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(exclude_none=True),
        headers=response_headers,
    )


def install_error_handlers(app: FastAPI) -> None:
    """Register every exception -> :class:`ErrorEnvelope` handler on ``app``.

    Registered (most specific first): the app's own :class:`AppError`, the
    domain conflicts (:class:`DuplicateNameError`, :class:`DuplicateColorError`,
    :class:`DuplicateUserError`), FastAPI request-validation and bare pydantic
    validation, any :class:`HTTPException`, and finally a catch-all for
    everything else as a non-leaking ``500``.
    """

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _render(
            exc.status_code,
            exc.code,
            exc.message,
            _new_request_id(),
            details=exc.details,
            headers=exc.headers,
        )

    @app.exception_handler(DuplicateNameError)
    async def _dup_name(_: Request, exc: DuplicateNameError) -> JSONResponse:
        return _render(409, ErrorCode.DUPLICATE_NAME, str(exc), _new_request_id())

    @app.exception_handler(DuplicateColorError)
    async def _dup_color(_: Request, exc: DuplicateColorError) -> JSONResponse:
        return _render(409, ErrorCode.DUPLICATE_COLOR, str(exc), _new_request_id())

    @app.exception_handler(DuplicateUserError)
    async def _dup_user(_: Request, exc: DuplicateUserError) -> JSONResponse:
        return _render(409, ErrorCode.DUPLICATE_USER, str(exc), _new_request_id())

    @app.exception_handler(RequestValidationError)
    async def _request_validation(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _render(
            422,
            ErrorCode.VALIDATION_ERROR,
            "the request is invalid",
            _new_request_id(),
            details=_field_errors(exc),
        )

    @app.exception_handler(ValidationError)
    async def _pydantic_validation(_: Request, exc: ValidationError) -> JSONResponse:
        # Reached for a bare pydantic ValidationError raised inside a route
        # (e.g. re-validating a merged PATCH result), which FastAPI does not
        # translate on its own.
        return _render(
            422,
            ErrorCode.VALIDATION_ERROR,
            "the request is invalid",
            _new_request_id(),
            details=_field_errors(exc),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODE_MAP.get(exc.status_code, ErrorCode.HTTP_ERROR)
        message = exc.detail if isinstance(exc.detail, str) else "request failed"
        headers = dict(exc.headers) if exc.headers else None
        return _render(
            exc.status_code, code, message, _new_request_id(), headers=headers
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        request_id = _new_request_id()
        # PALS's LAW: log the real cause server-side for diagnosis, but never
        # return it — the client sees only a generic message + request_id.
        _log.exception(
            "unhandled error [request_id=%s] %s %s",
            request_id,
            request.method,
            request.url.path,
        )
        return _render(
            500,
            ErrorCode.INTERNAL_ERROR,
            "an unexpected error occurred",
            request_id,
        )
