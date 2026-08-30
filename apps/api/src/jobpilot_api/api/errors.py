from __future__ import annotations

import logging
import re
import secrets
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

AUTH_API_PREFIX = "/api/v1/auth"
LOGGER = logging.getLogger(__name__)
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}")


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__()
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers


class ErrorDetail(BaseModel):
    field: str
    reason: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] | None = None
    request_id: str = Field(serialization_alias="requestId")


class ErrorResponse(BaseModel):
    error: ErrorBody


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

    @application.exception_handler(ApiError)
    async def handle_api_error(request: Request, error: ApiError) -> JSONResponse:
        return _error_response(
            request,
            error.status_code,
            error.code,
            error.message,
            headers=error.headers,
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in item["loc"][1:]) or "request",
                "reason": item["type"],
            }
            for item in error.errors()
        ]
        return _error_response(
            request,
            422,
            "VALIDATION_ERROR",
            "Request validation failed",
            details=details,
        )

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
    details: list[dict[str, str]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    error_body: dict[str, object] = {
        "code": code,
        "message": message,
        "requestId": request.state.request_id,
    }
    if details is not None:
        error_body["details"] = details
    response = JSONResponse(
        status_code=status_code,
        content={"error": error_body},
        headers=headers,
    )
    _attach_public_headers(request, response)
    return response


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
    path = request.url.path
    if path == AUTH_API_PREFIX or path.startswith(f"{AUTH_API_PREFIX}/"):
        response.headers["Cache-Control"] = "no-store"


def _new_request_id() -> str:
    return f"req_{secrets.token_urlsafe(18)}"
