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

from jobpilot_api.domain.web_session import IssuedWebSession, LoginTransaction, WebSession

CSRF_DERIVATION_CONTEXT = b"jobpilot-web-csrf-v1"
SESSION_ENTROPY_BYTES = 32
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
