from __future__ import annotations

import logging
import re
import secrets
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from jobpilot_api.domain.errors import DomainError

LOGGER = logging.getLogger(__name__)
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}")


def install_error_handlers(application: FastAPI) -> None:
    @application.middleware("http")
    async def handle_request_errors(request: Request, call_next):
        if request.state.request_id_is_invalid:
            return _error_response(
                request,
                400,
                "BAD_REQUEST",
                "Request could not be processed",
            )
        try:
            return await call_next(request)
        except Exception as error:
            return _unexpected_error_response(request, error)

    @application.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request,
        error: StarletteHTTPException,
    ) -> JSONResponse:
        if error.status_code == 404:
            code = "RESOURCE_NOT_FOUND"
            message = "Resource was not found"
        elif error.status_code == 405:
            code = "METHOD_NOT_ALLOWED"
            message = "Request method is not allowed"
        else:
            code = "BAD_REQUEST"
            message = "Request could not be processed"
        return _error_response(
            request,
            error.status_code,
            code,
            message,
            headers=error.headers,
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        _error: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(request, 422, "VALIDATION_ERROR", "Request validation failed")

    @application.exception_handler(DomainError)
    async def handle_domain_error(request: Request, error: DomainError) -> JSONResponse:
        return _error_response(request, error.status_code, error.code, error.message)

    @application.exception_handler(OperationalError)
    async def handle_database_error(request: Request, error: OperationalError) -> JSONResponse:
        message = str(error.orig).lower()
        if "locked" in message or "busy" in message:
            return _error_response(
                request,
                503,
                "DATABASE_BUSY",
                "Local database is temporarily busy",
            )
        return _unexpected_error_response(request, error)

    @application.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        return _unexpected_error_response(request, error)


def install_response_header_middleware(application: FastAPI) -> None:
    @application.middleware("http")
    async def attach_public_response_headers(request: Request, call_next):
        supplied_ids = request.headers.getlist("x-request-id")
        has_valid_supplied_id = (
            len(supplied_ids) == 1 and REQUEST_ID_PATTERN.fullmatch(supplied_ids[0]) is not None
        )
        request.state.request_id = supplied_ids[0] if has_valid_supplied_id else _new_request_id()
        request.state.request_id_is_invalid = bool(supplied_ids and not has_valid_supplied_id)
        response = await call_next(request)
        _attach_public_headers(request, response)
        return response


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    *,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    error_body: dict[str, object] = {
        "code": code,
        "message": message,
        "requestId": request.state.request_id,
    }
    response = JSONResponse(
        status_code=status_code,
        content={"error": error_body},
        headers=headers,
    )
    _attach_public_headers(request, response)
    return response


def public_error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    return _error_response(request, status_code, code, message)


def _unexpected_error_response(request: Request, error: Exception) -> JSONResponse:
    event = "api.unexpected_error"
    request_id = request.state.request_id
    exception_type = type(error).__name__
    LOGGER.error(
        "%s request_id=%s exception_type=%s",
        event,
        request_id,
        exception_type,
        extra={
            "event": event,
            "request_id": request_id,
            "exception_type": exception_type,
        },
    )
    return _error_response(
        request,
        500,
        "INTERNAL_ERROR",
        "An unexpected error occurred",
    )


def _attach_public_headers(request: Request, response: Response) -> None:
    response.headers["X-Request-Id"] = request.state.request_id


def _new_request_id() -> str:
    return f"req_{secrets.token_urlsafe(18)}"
