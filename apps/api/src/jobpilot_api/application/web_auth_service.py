from __future__ import annotations

import base64
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from jobpilot_api.application.identity_service import (
    AuthenticationRequiredError,
    IdentityConflictError,
    IdentityService,
    IdentityStoreUnavailableError,
    InvalidVerifiedIdentityError,
)
from jobpilot_api.application.web_session_service import (
    WebSessionIdentityNotFoundError,
    WebSessionPersistenceError,
    WebSessionService,
    WebSessionStoreUnavailableError,
    WebSessionUnitOfWork,
)
from jobpilot_api.domain.identity import LocalUser, VerifiedProviderIdentity
from jobpilot_api.domain.web_session import IssuedWebSession, LoginTransaction

WEB_LOGIN_TRANSACTION_MAX_AGE = 600
WEB_LOGIN_ENTROPY_BYTES = 32
WEB_LOGIN_OPAQUE_LENGTH = 43
WEB_LOGIN_INTENTS = frozenset({"login", "signup"})


class InvalidWebLoginRequestError(ValueError):
    """A Web login start request is outside the frozen public contract."""


class WebLoginRejectedError(Exception):
    """A Web login callback cannot establish an authenticated session."""


class WebLoginUnavailableError(Exception):
    """A required dependency cannot complete the Web authentication flow."""


class WebProviderRejectedError(Exception):
    """The provider response cannot establish a verified Web identity."""


class WebProviderEmailVerificationRequiredError(WebProviderRejectedError):
    """The provider identity has not completed email verification."""


class WebProviderUnavailableError(Exception):
    """The configured Web identity provider is temporarily unavailable."""


class WebAuthProvider(Protocol):
    def authorization_url(
        self,
        *,
        intent: str,
        state: str,
        nonce: str,
        pkce_verifier: str,
    ) -> str: ...

    def exchange_code(
        self,
        *,
        code: str,
        pkce_verifier: str,
        expected_nonce_hash: bytes,
    ) -> VerifiedProviderIdentity: ...


@dataclass(frozen=True, slots=True)
class WebLoginStart:
    authorization_url: str = field(repr=False)
    browser_handle: str = field(repr=False)
    transaction_max_age: int


@dataclass(frozen=True, slots=True)
class WebLoginCompletion:
    user: LocalUser
    issued_session: IssuedWebSession
    return_to: str


class WebAuthService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], WebSessionUnitOfWork],
        identity_service: IdentityService,
        web_session_service: WebSessionService,
        provider: WebAuthProvider,
        *,
        token_factory: Callable[[], bytes],
        clock: Callable[[], datetime],
        allowed_return_paths: frozenset[str] = frozenset({"/"}),
    ) -> None:
        frozen_paths = frozenset(allowed_return_paths)
        if "/" not in frozen_paths or any(
            not _is_safe_relative_path(path) for path in frozen_paths
        ):
            raise ValueError("allowed return paths must contain only safe relative paths")
        self._unit_of_work_factory = unit_of_work_factory
        self._identity_service = identity_service
        self._web_session_service = web_session_service
        self._provider = provider
        self._token_factory = token_factory
        self._clock = clock
        self._allowed_return_paths = frozen_paths

    def begin(self, intent: str | None, return_to: str | None) -> WebLoginStart:
        if not isinstance(intent, str) or intent not in WEB_LOGIN_INTENTS:
            raise InvalidWebLoginRequestError
        resolved_return_to = "/" if return_to is None else return_to
        if (
            not isinstance(resolved_return_to, str)
            or resolved_return_to not in self._allowed_return_paths
            or not _is_safe_relative_path(resolved_return_to)
        ):
            raise InvalidWebLoginRequestError

        now = _require_aware_datetime(self._clock())
        browser_handle = _new_opaque_value(self._token_factory)
        state = _new_opaque_value(self._token_factory)
        nonce = _new_opaque_value(self._token_factory)
        pkce_verifier = _new_opaque_value(self._token_factory)
        authorization_url = self._provider.authorization_url(
            intent=intent,
            state=state,
            nonce=nonce,
            pkce_verifier=pkce_verifier,
        )

        try:
            with self._unit_of_work_factory() as unit_of_work:
                unit_of_work.login_transactions.delete_expired(now=now)
                unit_of_work.login_transactions.create(
                    browser_handle_hash=_hash_opaque_value(browser_handle),
                    state_hash=_hash_opaque_value(state),
                    nonce_hash=_hash_opaque_value(nonce),
                    pkce_verifier=pkce_verifier,
                    intent=intent,
                    return_to=resolved_return_to,
                    created_at=now,
                    expires_at=now + timedelta(seconds=WEB_LOGIN_TRANSACTION_MAX_AGE),
                )
                unit_of_work.commit()
        except WebSessionPersistenceError:
            raise WebLoginUnavailableError from None

        return WebLoginStart(
            authorization_url=authorization_url,
            browser_handle=browser_handle,
            transaction_max_age=WEB_LOGIN_TRANSACTION_MAX_AGE,
        )

    def complete(
        self,
        browser_handle: str | None,
        state: str | None,
        code: str | None,
        provider_error: bool = False,
    ) -> WebLoginCompletion:
        now = _require_aware_datetime(self._clock())
        try:
            transaction = self._consume_transaction(
                browser_handle_hash=_hash_presented_value(browser_handle),
                state_hash=_hash_presented_value(state),
                now=now,
            )
        except WebSessionPersistenceError:
            raise WebLoginUnavailableError from None
        if transaction is None or provider_error or not isinstance(code, str) or not code:
            raise WebLoginRejectedError

        try:
            identity = self._provider.exchange_code(
                code=code,
                pkce_verifier=transaction.pkce_verifier,
                expected_nonce_hash=transaction.nonce_hash,
            )
        except WebProviderRejectedError:
            raise WebLoginRejectedError from None
        except WebProviderUnavailableError:
            raise WebLoginUnavailableError from None

        try:
            user = self._identity_service.provision(identity)
        except (
            AuthenticationRequiredError,
            IdentityConflictError,
            InvalidVerifiedIdentityError,
        ):
            raise WebLoginRejectedError from None
        except IdentityStoreUnavailableError:
            raise WebLoginUnavailableError from None

        try:
            issued_session = self._web_session_service.issue(
                user_id=user.id,
                identity_issuer=identity.issuer,
                identity_subject=identity.subject,
            )
        except WebSessionIdentityNotFoundError:
            raise WebLoginRejectedError from None
        except WebSessionStoreUnavailableError:
            raise WebLoginUnavailableError from None
        return WebLoginCompletion(
            user=user,
            issued_session=issued_session,
            return_to=transaction.return_to,
        )

    def _consume_transaction(
        self,
        *,
        browser_handle_hash: bytes | None,
        state_hash: bytes | None,
        now: datetime,
    ) -> LoginTransaction | None:
        with self._unit_of_work_factory() as unit_of_work:
            transaction = unit_of_work.login_transactions.consume(
                browser_handle_hash=browser_handle_hash,
                state_hash=state_hash,
                now=now,
            )
            unit_of_work.commit()
        return transaction


def _new_opaque_value(token_factory: Callable[[], bytes]) -> str:
    entropy = token_factory()
    if not isinstance(entropy, bytes) or len(entropy) != WEB_LOGIN_ENTROPY_BYTES:
        raise InvalidWebLoginRequestError
    return _base64url_encode(entropy)


def _hash_presented_value(value: str | None) -> bytes | None:
    if not isinstance(value, str) or not _is_canonical_opaque_value(value):
        return None
    return _hash_opaque_value(value)


def _hash_opaque_value(value: str) -> bytes:
    return hashlib.sha256(value.encode("ascii")).digest()


def _is_canonical_opaque_value(value: str) -> bool:
    if len(value) != WEB_LOGIN_OPAQUE_LENGTH:
        return False
    try:
        encoded = value.encode("ascii")
        padding = b"=" * (-len(encoded) % 4)
        entropy = base64.b64decode(encoded + padding, altchars=b"-_", validate=True)
    except (UnicodeEncodeError, ValueError):
        return False
    return len(entropy) == WEB_LOGIN_ENTROPY_BYTES and _base64url_encode(entropy) == value


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _require_aware_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("Web auth clock must be timezone-aware")
    return value


def _is_safe_relative_path(path: object) -> bool:
    return (
        isinstance(path, str)
        and path.startswith("/")
        and not path.startswith("//")
        and "\\" not in path
        and "?" not in path
        and "#" not in path
        and not any(ord(character) < 32 for character in path)
    )
