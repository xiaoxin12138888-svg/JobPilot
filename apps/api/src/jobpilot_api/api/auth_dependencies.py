from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from jobpilot_api.application.identity_service import (
    AuthenticationRequiredError,
    IdentityService,
    IdentityStoreUnavailableError,
    InvalidProfileUpdateError,
    InvalidVerifiedIdentityError,
)
from jobpilot_api.application.web_auth_service import WebAuthService
from jobpilot_api.application.web_session_service import (
    WebSessionAuthenticationRequiredError,
    WebSessionCsrfRejectedError,
    WebSessionService,
    WebSessionStoreUnavailableError,
)
from jobpilot_api.domain.identity import AuthenticatedUser, SessionKind, VerifiedProviderIdentity
from jobpilot_api.domain.web_session import AuthenticatedWebSession
from jobpilot_api.infrastructure.auth.access_token_validator import (
    EmailVerificationRequiredError,
    ExtensionAccessTokenValidator,
    IdentityProviderUnavailableError,
    InvalidAccessTokenError,
)

from .errors import ApiError
from .login_rate_limit import WebLoginRateLimiter

WEB_SESSION_COOKIE_NAMES = frozenset({"__Host-jobpilot_session", "jobpilot_dev_session"})


@dataclass(frozen=True, slots=True)
class WebAuthRuntime:
    service: WebAuthService
    session_service: WebSessionService
    login_rate_limiter: WebLoginRateLimiter
    web_origin: str
    transaction_cookie_name: str
    session_cookie_name: str
    cookie_secure: bool
    session_max_age: int


@dataclass(frozen=True, slots=True)
class AuthRuntime:
    access_token_validator: ExtensionAccessTokenValidator
    identity_service: IdentityService
    web: WebAuthRuntime


def get_auth_runtime(request: Request) -> AuthRuntime:
    runtime = getattr(request.app.state, "auth_runtime", None)
    if not isinstance(runtime, AuthRuntime):
        raise ApiError(503, "SERVICE_NOT_READY", "Authentication service is not configured")
    return runtime


AuthRuntimeDependency = Annotated[AuthRuntime, Depends(get_auth_runtime)]


def get_verified_extension_identity(
    request: Request,
    runtime: AuthRuntimeDependency,
) -> VerifiedProviderIdentity:
    raw_token = _extract_bearer_token(request)
    try:
        return runtime.access_token_validator.validate(raw_token)
    except InvalidAccessTokenError:
        raise _authentication_required() from None
    except EmailVerificationRequiredError:
        raise ApiError(
            403, "EMAIL_VERIFICATION_REQUIRED", "Email verification is required"
        ) from None
    except IdentityProviderUnavailableError:
        raise ApiError(
            503,
            "IDENTITY_PROVIDER_UNAVAILABLE",
            "Identity provider is temporarily unavailable",
        ) from None


VerifiedIdentityDependency = Annotated[
    VerifiedProviderIdentity,
    Depends(get_verified_extension_identity),
]


def get_current_user(
    request: Request,
    runtime: AuthRuntimeDependency,
) -> AuthenticatedUser:
    _reject_query_credentials(request)
    authorization_values = request.headers.getlist("authorization")
    web_credentials = _reserved_web_cookie_credentials(request)
    _reject_ambiguous_credentials(authorization_values, web_credentials)

    if authorization_values:
        identity = get_verified_extension_identity(request, runtime)
        return _authenticate_extension_identity(identity, runtime)

    session_secret = _current_web_session_secret(web_credentials, runtime.web)
    if session_secret is None:
        raise _authentication_required()

    try:
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            require_web_origin_and_fetch(request, runtime)
            resolved = runtime.web.session_service.authenticate_with_csrf(
                session_secret,
                _single_header(request, "x-csrf-token"),
            )
        else:
            resolved = runtime.web.session_service.authenticate(session_secret)
    except WebSessionAuthenticationRequiredError:
        raise _authentication_required() from None
    except WebSessionCsrfRejectedError:
        raise _forbidden() from None
    except WebSessionStoreUnavailableError:
        raise _dependency_unavailable() from None
    return resolved.authenticated_user


def _authenticate_extension_identity(
    identity: VerifiedProviderIdentity,
    runtime: AuthRuntime,
) -> AuthenticatedUser:
    try:
        return runtime.identity_service.authenticate_existing(
            identity,
            session_kind=SessionKind.EXTENSION,
        )
    except AuthenticationRequiredError:
        raise _authentication_required() from None
    except IdentityStoreUnavailableError:
        raise _dependency_unavailable() from None


CurrentUserDependency = Annotated[AuthenticatedUser, Depends(get_current_user)]


def get_current_web_session(
    request: Request,
    runtime: AuthRuntimeDependency,
) -> AuthenticatedWebSession:
    _reject_query_credentials(request)
    authorization_values = request.headers.getlist("authorization")
    web_credentials = _reserved_web_cookie_credentials(request)
    _reject_ambiguous_credentials(authorization_values, web_credentials)
    if authorization_values:
        raise _authentication_required(include_bearer_challenge=False)

    session_secret = _current_web_session_secret(web_credentials, runtime.web)
    if session_secret is None:
        raise _authentication_required(include_bearer_challenge=False)
    try:
        return runtime.web.session_service.authenticate(session_secret)
    except WebSessionAuthenticationRequiredError:
        raise _authentication_required(include_bearer_challenge=False) from None
    except WebSessionStoreUnavailableError:
        raise _dependency_unavailable() from None


CurrentWebSessionDependency = Annotated[AuthenticatedWebSession, Depends(get_current_web_session)]


def require_web_origin_and_fetch(
    request: Request,
    runtime: AuthRuntimeDependency,
) -> None:
    origins = request.headers.getlist("origin")
    fetch_sites = request.headers.getlist("sec-fetch-site")
    if origins != [runtime.web.web_origin] or fetch_sites not in [
        ["same-origin"],
        ["same-site"],
    ]:
        raise _forbidden()


def resolve_web_logout_credentials(
    request: Request,
    runtime: AuthRuntime,
) -> tuple[str | None, str | None]:
    _reject_query_credentials(request)
    authorization_values = request.headers.getlist("authorization")
    web_credentials = _reserved_web_cookie_credentials(request)
    _reject_ambiguous_credentials(authorization_values, web_credentials)
    if authorization_values:
        raise ApiError(400, "BAD_REQUEST", "Bearer credentials are not accepted")
    return (
        _current_web_session_secret(web_credentials, runtime.web),
        _single_header(request, "x-csrf-token"),
    )


async def require_empty_body(request: Request) -> None:
    content_length = request.headers.get("content-length")
    if content_length not in (None, "0"):
        raise ApiError(422, "VALIDATION_ERROR", "Request validation failed")
    async for chunk in request.stream():
        if chunk:
            raise ApiError(422, "VALIDATION_ERROR", "Request validation failed")


def map_identity_service_error(error: Exception) -> ApiError:
    if isinstance(error, (AuthenticationRequiredError, InvalidVerifiedIdentityError)):
        return _authentication_required()
    if isinstance(error, IdentityStoreUnavailableError):
        return _dependency_unavailable()
    if isinstance(error, InvalidProfileUpdateError):
        return ApiError(422, "VALIDATION_ERROR", "Request validation failed")
    raise error


def _extract_bearer_token(request: Request) -> str:
    _reject_query_credentials(request)

    authorization_values = request.headers.getlist("authorization")
    has_web_session = bool(_reserved_web_cookie_credentials(request))
    if authorization_values and has_web_session:
        raise ApiError(
            400,
            "AMBIGUOUS_CREDENTIALS",
            "Multiple authentication credentials are not allowed",
        )
    if len(authorization_values) != 1:
        raise _authentication_required()

    scheme, separator, raw_token = authorization_values[0].partition(" ")
    if (
        separator != " "
        or scheme.lower() != "bearer"
        or not raw_token
        or raw_token != raw_token.strip()
        or any(character.isspace() for character in raw_token)
    ):
        raise _authentication_required()
    return raw_token


def _authentication_required(*, include_bearer_challenge: bool = True) -> ApiError:
    headers = {"WWW-Authenticate": "Bearer"} if include_bearer_challenge else None
    return ApiError(
        401,
        "AUTHENTICATION_REQUIRED",
        "Authentication is required",
        headers=headers,
    )


def _dependency_unavailable() -> ApiError:
    return ApiError(
        503,
        "DEPENDENCY_UNAVAILABLE",
        "A required dependency is temporarily unavailable",
    )


def _forbidden() -> ApiError:
    return ApiError(403, "FORBIDDEN", "Request is not permitted")


def _reserved_web_cookie_credentials(request: Request) -> list[tuple[str, str]]:
    credentials: list[tuple[str, str]] = []
    for raw_cookie_header in request.headers.getlist("cookie"):
        for raw_pair in raw_cookie_header.split(";"):
            name, separator, value = raw_pair.strip().partition("=")
            if separator and name in WEB_SESSION_COOKIE_NAMES:
                credentials.append((name, value))
    return credentials


def _reject_ambiguous_credentials(
    authorization_values: list[str],
    web_credentials: list[tuple[str, str]],
) -> None:
    if (authorization_values and web_credentials) or len(web_credentials) > 1:
        raise ApiError(
            400,
            "AMBIGUOUS_CREDENTIALS",
            "Multiple authentication credentials are not allowed",
        )


def _current_web_session_secret(
    credentials: list[tuple[str, str]],
    runtime: WebAuthRuntime,
) -> str | None:
    if len(credentials) != 1 or credentials[0][0] != runtime.session_cookie_name:
        return None
    return credentials[0][1]


def _single_header(request: Request, name: str) -> str | None:
    values = request.headers.getlist(name)
    return values[0] if len(values) == 1 else None


def _reject_query_credentials(request: Request) -> None:
    if "access_token" in request.query_params:
        raise ApiError(400, "BAD_REQUEST", "Query credentials are not allowed")
