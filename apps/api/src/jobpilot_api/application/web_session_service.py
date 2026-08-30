from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Protocol
from uuid import UUID

from jobpilot_api.domain.identity import AuthenticatedUser, SessionKind
from jobpilot_api.domain.web_session import (
    AuthenticatedWebSession,
    IssuedWebSession,
    LoginTransaction,
    WebSession,
)

CSRF_DERIVATION_CONTEXT = b"jobpilot-web-csrf-v1"
SESSION_ENTROPY_BYTES = 32
SESSION_SECRET_LENGTH = 43
DEFAULT_IDLE_TIMEOUT = timedelta(days=7)
DEFAULT_ABSOLUTE_TIMEOUT = timedelta(days=30)


class InvalidSessionSecretError(ValueError):
    """A session secret does not satisfy the opaque 256-bit contract."""


class WebSessionIdentityNotFoundError(Exception):
    """The requested local user and provider identity mapping does not exist."""


class WebSessionPersistenceError(Exception):
    """Web authentication persistence could not establish a trustworthy outcome."""


class WebSessionStoreUnavailableError(Exception):
    """The Web session store could not establish a trustworthy outcome."""


class WebSessionAuthenticationRequiredError(Exception):
    """A presented Web session cannot authenticate a local user."""


class WebSessionCsrfRejectedError(Exception):
    """A session-bound CSRF proof is missing or invalid."""


class WebSessionRepository(Protocol):
    def create(
        self,
        *,
        user_id: UUID,
        identity_issuer: str,
        identity_subject: str,
        session_token_hash: bytes,
        csrf_token_hash: bytes,
        created_at: datetime,
        last_used_at: datetime,
        idle_expires_at: datetime,
        absolute_expires_at: datetime,
    ) -> WebSession: ...

    def find_active_by_token_hash(
        self,
        session_token_hash: bytes,
        *,
        now: datetime,
    ) -> WebSession | None: ...

    def lock_active_by_token_hash(
        self,
        session_token_hash: bytes,
        *,
        now: datetime,
    ) -> WebSession | None: ...

    def touch(
        self,
        session_id: UUID,
        *,
        last_used_at: datetime,
        idle_expires_at: datetime,
    ) -> None: ...

    def revoke(self, session_id: UUID, *, revoked_at: datetime) -> None: ...


class LoginTransactionRepository(Protocol):
    def delete_expired(self, *, now: datetime) -> None: ...

    def create(
        self,
        *,
        browser_handle_hash: bytes,
        state_hash: bytes,
        nonce_hash: bytes,
        pkce_verifier: str,
        intent: str,
        return_to: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> LoginTransaction: ...

    def consume(
        self,
        *,
        browser_handle_hash: bytes | None,
        state_hash: bytes | None,
        now: datetime,
    ) -> LoginTransaction | None: ...


class WebSessionUnitOfWork(Protocol):
    sessions: WebSessionRepository
    login_transactions: LoginTransactionRepository

    def __enter__(self) -> WebSessionUnitOfWork: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


class WebSessionService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], WebSessionUnitOfWork],
        *,
        token_factory: Callable[[], bytes] = lambda: secrets.token_bytes(SESSION_ENTROPY_BYTES),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        idle_timeout: timedelta = DEFAULT_IDLE_TIMEOUT,
        absolute_timeout: timedelta = DEFAULT_ABSOLUTE_TIMEOUT,
    ) -> None:
        if idle_timeout <= timedelta(0):
            raise ValueError("idle timeout must be positive")
        if absolute_timeout < idle_timeout:
            raise ValueError("absolute timeout must not be shorter than idle timeout")
        self._unit_of_work_factory = unit_of_work_factory
        self._token_factory = token_factory
        self._clock = clock
        self._idle_timeout = idle_timeout
        self._absolute_timeout = absolute_timeout

    def issue(
        self,
        *,
        user_id: UUID,
        identity_issuer: str,
        identity_subject: str,
    ) -> IssuedWebSession:
        session_secret = _encode_session_secret(self._token_factory())
        csrf_token = derive_csrf_token(session_secret)
        now = self._clock()
        if now.utcoffset() is None:
            raise ValueError("session clock must be timezone-aware")

        try:
            with self._unit_of_work_factory() as unit_of_work:
                session = unit_of_work.sessions.create(
                    user_id=user_id,
                    identity_issuer=identity_issuer,
                    identity_subject=identity_subject,
                    session_token_hash=hash_browser_secret(session_secret),
                    csrf_token_hash=hash_browser_secret(csrf_token),
                    created_at=now,
                    last_used_at=now,
                    idle_expires_at=now + self._idle_timeout,
                    absolute_expires_at=now + self._absolute_timeout,
                )
                unit_of_work.commit()
        except WebSessionPersistenceError as error:
            raise WebSessionStoreUnavailableError from error

        return IssuedWebSession(
            session=session,
            session_secret=session_secret,
            csrf_token=csrf_token,
        )

    def authenticate(self, session_secret: str | None) -> AuthenticatedWebSession:
        return self._authenticate(session_secret, presented_csrf=_CSRF_NOT_REQUIRED)

    def authenticate_with_csrf(
        self,
        session_secret: str | None,
        csrf_token: str | None,
    ) -> AuthenticatedWebSession:
        return self._authenticate(session_secret, presented_csrf=csrf_token)

    def logout(self, session_secret: str | None, csrf_token: str | None) -> None:
        canonical_secret = _optional_canonical_session_secret(session_secret)
        if canonical_secret is None:
            return
        now = _require_aware_session_time(self._clock())

        try:
            with self._unit_of_work_factory() as unit_of_work:
                session = unit_of_work.sessions.lock_active_by_token_hash(
                    hash_browser_secret(canonical_secret),
                    now=now,
                )
                if session is None:
                    return
                expected_csrf = derive_csrf_token(canonical_secret)
                _require_persisted_csrf_binding(session, expected_csrf)
                if not _matches_csrf_token(csrf_token, expected_csrf):
                    raise WebSessionCsrfRejectedError
                unit_of_work.sessions.revoke(session.id, revoked_at=now)
                unit_of_work.commit()
        except WebSessionPersistenceError as error:
            raise WebSessionStoreUnavailableError from error

    def _authenticate(
        self,
        session_secret: str | None,
        *,
        presented_csrf: object,
    ) -> AuthenticatedWebSession:
        canonical_secret = _required_canonical_session_secret(session_secret)
        now = _require_aware_session_time(self._clock())

        try:
            with self._unit_of_work_factory() as unit_of_work:
                session = unit_of_work.sessions.lock_active_by_token_hash(
                    hash_browser_secret(canonical_secret),
                    now=now,
                )
                if session is None:
                    raise WebSessionAuthenticationRequiredError

                expected_csrf = derive_csrf_token(canonical_secret)
                _require_persisted_csrf_binding(session, expected_csrf)
                if presented_csrf is not _CSRF_NOT_REQUIRED and not _matches_csrf_token(
                    presented_csrf,
                    expected_csrf,
                ):
                    raise WebSessionCsrfRejectedError

                unit_of_work.sessions.touch(
                    session.id,
                    last_used_at=now,
                    idle_expires_at=min(now + self._idle_timeout, session.absolute_expires_at),
                )
                unit_of_work.commit()
        except WebSessionPersistenceError as error:
            raise WebSessionStoreUnavailableError from error

        return AuthenticatedWebSession(
            authenticated_user=AuthenticatedUser(
                user_id=session.user_id,
                identity_issuer=session.identity_issuer,
                identity_subject=session.identity_subject,
                session_kind=SessionKind.WEB,
                session_id=session.id,
            ),
            csrf_token=expected_csrf,
        )


def derive_csrf_token(session_secret: str) -> str:
    entropy = _decode_session_secret(session_secret)
    derived = hmac.digest(entropy, CSRF_DERIVATION_CONTEXT, hashlib.sha256)
    return _base64url_encode(derived)


def hash_browser_secret(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("ascii")).digest()


def _encode_session_secret(entropy: bytes) -> str:
    if not isinstance(entropy, bytes) or len(entropy) != SESSION_ENTROPY_BYTES:
        raise InvalidSessionSecretError
    return _base64url_encode(entropy)


def _decode_session_secret(session_secret: str) -> bytes:
    if not isinstance(session_secret, str) or len(session_secret) != SESSION_SECRET_LENGTH:
        raise InvalidSessionSecretError
    try:
        encoded = session_secret.encode("ascii")
        padding = b"=" * (-len(encoded) % 4)
        entropy = base64.b64decode(encoded + padding, altchars=b"-_", validate=True)
    except (UnicodeEncodeError, ValueError):
        raise InvalidSessionSecretError from None
    if len(entropy) != SESSION_ENTROPY_BYTES or _base64url_encode(entropy) != session_secret:
        raise InvalidSessionSecretError
    return entropy


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


_CSRF_NOT_REQUIRED = object()


def _required_canonical_session_secret(session_secret: str | None) -> str:
    canonical = _optional_canonical_session_secret(session_secret)
    if canonical is None:
        raise WebSessionAuthenticationRequiredError
    return canonical


def _optional_canonical_session_secret(session_secret: str | None) -> str | None:
    if not isinstance(session_secret, str):
        return None
    try:
        _decode_session_secret(session_secret)
    except InvalidSessionSecretError:
        return None
    return session_secret


def _require_aware_session_time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("session clock must be timezone-aware")
    return value


def _require_persisted_csrf_binding(session: WebSession, expected_csrf: str) -> None:
    if not hmac.compare_digest(session.csrf_token_hash, hash_browser_secret(expected_csrf)):
        raise WebSessionStoreUnavailableError


def _matches_csrf_token(presented: object, expected: str) -> bool:
    if not isinstance(presented, str) or len(presented) != len(expected):
        return False
    try:
        presented_bytes = presented.encode("ascii")
    except UnicodeEncodeError:
        return False
    return hmac.compare_digest(presented_bytes, expected.encode("ascii"))
