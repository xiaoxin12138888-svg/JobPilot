from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from jobpilot_api.application.web_auth_service import (
    InvalidWebLoginRequestError,
    WebLoginRejectedError,
    WebLoginUnavailableError,
)

from .auth_dependencies import AuthRuntimeDependency, WebAuthRuntime
from .errors import ApiError, ErrorResponse

LOGGER = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/auth/web",
    tags=["authentication"],
)

AUTHORIZE_OPENAPI_PARAMETERS = [
    {
        "name": "intent",
        "in": "query",
        "required": True,
        "schema": {"type": "string", "enum": ["login", "signup"]},
    },
    {
        "name": "returnTo",
        "in": "query",
        "required": False,
        "schema": {"type": "string"},
    },
]
CALLBACK_OPENAPI_PARAMETERS = [
    {"name": name, "in": "query", "required": False, "schema": {"type": "string"}}
    for name in ("code", "state", "error")
]


@router.get(
    "/authorize",
    response_class=RedirectResponse,
    status_code=302,
    responses={
        400: {"model": ErrorResponse},
        429: {
            "model": ErrorResponse,
            "headers": {
                "Retry-After": {
                    "schema": {"type": "integer", "minimum": 1},
                    "description": "Seconds until another login start may be attempted",
                }
            },
        },
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    openapi_extra={"parameters": AUTHORIZE_OPENAPI_PARAMETERS, "security": []},
)
def begin_web_login(
    request: Request,
    runtime: AuthRuntimeDependency,
) -> RedirectResponse:
    retry_after = runtime.web.login_rate_limiter.check(_client_key(request))
    if retry_after is not None:
        raise ApiError(
            429,
            "RATE_LIMITED",
            "Too many authentication attempts",
            headers={"Retry-After": str(retry_after)},
        )
    if _has_duplicate_query_parameter(request, "intent") or _has_duplicate_query_parameter(
        request, "returnTo"
    ):
        raise _bad_login_request()
    intent = request.query_params.get("intent")
    return_to = request.query_params.get("returnTo")
    try:
        started = runtime.web.service.begin(intent=intent, return_to=return_to)
    except InvalidWebLoginRequestError:
        raise _bad_login_request() from None
    except WebLoginUnavailableError:
        raise ApiError(
            503,
            "DEPENDENCY_UNAVAILABLE",
            "A required dependency is temporarily unavailable",
        ) from None

    response = _navigation_redirect(started.authorization_url, status_code=302)
    _set_transaction_cookie(
        response,
        runtime.web,
        started.browser_handle,
        max_age=started.transaction_max_age,
    )
    return response


@router.get(
    "/callback",
    response_class=RedirectResponse,
    status_code=303,
    responses={500: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    openapi_extra={"parameters": CALLBACK_OPENAPI_PARAMETERS, "security": []},
)
def complete_web_login(
    request: Request,
    runtime: AuthRuntimeDependency,
) -> RedirectResponse:
    duplicate_code = _has_duplicate_query_parameter(request, "code")
    duplicate_state = _has_duplicate_query_parameter(request, "state")
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")
    browser_handle = request.cookies.get(runtime.web.transaction_cookie_name)
    try:
        completed = runtime.web.service.complete(
            browser_handle=browser_handle,
            state=None if duplicate_state else state,
            code=None if duplicate_code else code,
            provider_error=error is not None or duplicate_code or duplicate_state,
        )
    except (WebLoginRejectedError, WebLoginUnavailableError):
        return _callback_failure_response(runtime.web)
    except Exception as error:
        _log_callback_unexpected_error(request, error)
        return _callback_failure_response(runtime.web)

    response = _navigation_redirect(
        f"{runtime.web.web_origin}{completed.return_to}",
        status_code=303,
    )
    _delete_transaction_cookie(response, runtime.web)
    response.set_cookie(
        key=runtime.web.session_cookie_name,
        value=completed.issued_session.session_secret,
        max_age=runtime.web.session_max_age,
        httponly=True,
        secure=runtime.web.cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


def _set_transaction_cookie(
    response: RedirectResponse,
    runtime: WebAuthRuntime,
    browser_handle: str,
    *,
    max_age: int,
) -> None:
    response.set_cookie(
        key=runtime.transaction_cookie_name,
        value=browser_handle,
        max_age=max_age,
        httponly=True,
        secure=runtime.cookie_secure,
        samesite="lax",
        path="/",
    )


def _delete_transaction_cookie(
    response: RedirectResponse,
    runtime: WebAuthRuntime,
) -> None:
    response.delete_cookie(
        key=runtime.transaction_cookie_name,
        httponly=True,
        secure=runtime.cookie_secure,
        samesite="lax",
        path="/",
    )


def _callback_failure_response(runtime: WebAuthRuntime) -> RedirectResponse:
    response = _navigation_redirect(
        f"{runtime.web_origin}/auth/error",
        status_code=303,
    )
    _delete_transaction_cookie(response, runtime)
    return response


def _log_callback_unexpected_error(request: Request, error: Exception) -> None:
    event = "auth.web_callback_unexpected_error"
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


def _has_duplicate_query_parameter(request: Request, name: str) -> bool:
    return len(request.query_params.getlist(name)) > 1


def _client_key(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def _navigation_redirect(location: str, *, status_code: int) -> RedirectResponse:
    return RedirectResponse(
        location,
        status_code=status_code,
        headers={"Referrer-Policy": "no-referrer"},
    )


def _bad_login_request() -> ApiError:
    return ApiError(400, "BAD_REQUEST", "Request could not be processed")
