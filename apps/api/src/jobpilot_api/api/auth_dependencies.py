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
from jobpilot_api.domain.identity import AuthenticatedUser, SessionKind, VerifiedProviderIdentity
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
    identity: VerifiedIdentityDependency,
    runtime: AuthRuntimeDependency,
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
    if "access_token" in request.query_params:
        raise ApiError(400, "BAD_REQUEST", "Query credentials are not allowed")

    authorization_values = request.headers.getlist("authorization")
    has_web_session = any(name in request.cookies for name in WEB_SESSION_COOKIE_NAMES)
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


def _authentication_required() -> ApiError:
    return ApiError(
        401,
        "AUTHENTICATION_REQUIRED",
        "Authentication is required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _dependency_unavailable() -> ApiError:
    return ApiError(
        503,
        "DEPENDENCY_UNAVAILABLE",
        "A required dependency is temporarily unavailable",
    )
