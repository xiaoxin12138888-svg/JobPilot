from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

import jobpilot_api.application.web_session_service as web_session_module
from jobpilot_api.application.web_session_service import (
    CSRF_DERIVATION_CONTEXT,
    InvalidSessionSecretError,
    WebSessionPersistenceError,
    WebSessionService,
    WebSessionStoreUnavailableError,
    derive_csrf_token,
    hash_browser_secret,
)
from jobpilot_api.domain.identity import SessionKind
from jobpilot_api.domain.web_session import WebSession

SESSION_SECRET = base64.urlsafe_b64encode(bytes(range(32))).rstrip(b"=").decode("ascii")
OTHER_SESSION_SECRET = (
    base64.urlsafe_b64encode(bytes(reversed(range(32)))).rstrip(b"=").decode("ascii")
)


class RecordingWebSessionRepository:
    def __init__(
        self,
        *,
        active_session: WebSession | None = None,
        lookup_error: Exception | None = None,
    ) -> None:
        self.create_call: dict[str, object] | None = None
        self.active_session = active_session
        self.lookup_error = lookup_error
        self.lock_calls: list[dict[str, object]] = []
        self.touch_calls: list[dict[str, object]] = []
        self.revoke_calls: list[dict[str, object]] = []

    def create(self, **values: object) -> WebSession:
        self.create_call = values
        return WebSession(
            id=uuid4(),
            user_id=values["user_id"],  # type: ignore[arg-type]
            identity_issuer=values["identity_issuer"],  # type: ignore[arg-type]
            identity_subject=values["identity_subject"],  # type: ignore[arg-type]
            csrf_token_hash=values["csrf_token_hash"],  # type: ignore[arg-type]
            created_at=values["created_at"],  # type: ignore[arg-type]
            last_used_at=values["last_used_at"],  # type: ignore[arg-type]
            idle_expires_at=values["idle_expires_at"],  # type: ignore[arg-type]
            absolute_expires_at=values["absolute_expires_at"],  # type: ignore[arg-type]
            revoked_at=None,
        )

    def lock_active_by_token_hash(
        self,
        session_token_hash: bytes,
        *,
        now: datetime,
    ) -> WebSession | None:
        self.lock_calls.append(
            {
                "session_token_hash": session_token_hash,
                "now": now,
            }
        )
        if self.lookup_error is not None:
            raise self.lookup_error
        return self.active_session

    def touch(
        self,
        session_id: object,
        *,
        last_used_at: datetime,
        idle_expires_at: datetime,
    ) -> None:
        self.touch_calls.append(
            {
                "session_id": session_id,
                "last_used_at": last_used_at,
                "idle_expires_at": idle_expires_at,
            }
        )

    def revoke(self, session_id: object, *, revoked_at: datetime) -> None:
        self.revoke_calls.append(
            {
                "session_id": session_id,
                "revoked_at": revoked_at,
            }
        )


class RecordingWebSessionUnitOfWork:
    def __init__(
        self,
        repository: RecordingWebSessionRepository,
        *,
        commit_error: Exception | None = None,
    ) -> None:
        self.sessions = repository
        self.login_transactions = object()
        self.commit_count = 0
        self.commit_error = commit_error

    def __enter__(self) -> RecordingWebSessionUnitOfWork:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def commit(self) -> None:
        self.commit_count += 1
        if self.commit_error is not None:
            raise self.commit_error


def _active_session(
    *,
    now: datetime,
    absolute_expires_at: datetime | None = None,
    csrf_token_hash: bytes | None = None,
) -> WebSession:
    return WebSession(
        id=uuid4(),
        user_id=uuid4(),
        identity_issuer="https://tenant.example.invalid/",
        identity_subject="auth0|subject-1",
        csrf_token_hash=(
            hash_browser_secret(derive_csrf_token(SESSION_SECRET))
            if csrf_token_hash is None
            else csrf_token_hash
        ),
        created_at=now - timedelta(days=25),
        last_used_at=now - timedelta(days=1),
        idle_expires_at=now + timedelta(days=1),
        absolute_expires_at=absolute_expires_at or now + timedelta(days=5),
        revoked_at=None,
    )


def _expected_error_type(name: str) -> type[Exception]:
    error_type = getattr(web_session_module, name, None)
    assert isinstance(error_type, type) and issubclass(error_type, Exception), (
        f"web session application boundary must define {name}"
    )
    return error_type


def test_issue_derives_session_bound_csrf_and_persists_only_hashes() -> None:
    raw_entropy = bytes(range(32))
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    user_id = uuid4()
    repository = RecordingWebSessionRepository()
    unit_of_work = RecordingWebSessionUnitOfWork(repository)
    service = WebSessionService(
        lambda: unit_of_work,
        token_factory=lambda: raw_entropy,
        clock=lambda: now,
        idle_timeout=timedelta(days=7),
        absolute_timeout=timedelta(days=30),
    )

    issued = service.issue(
        user_id=user_id,
        identity_issuer="https://tenant.example.invalid/",
        identity_subject="auth0|subject-1",
    )

    expected_session_secret = base64.urlsafe_b64encode(raw_entropy).rstrip(b"=").decode()
    expected_csrf_token = (
        base64.urlsafe_b64encode(hmac.digest(raw_entropy, CSRF_DERIVATION_CONTEXT, hashlib.sha256))
        .rstrip(b"=")
        .decode()
    )
    assert issued.session_secret == expected_session_secret
    assert issued.csrf_token == expected_csrf_token
    assert repository.create_call == {
        "user_id": user_id,
        "identity_issuer": "https://tenant.example.invalid/",
        "identity_subject": "auth0|subject-1",
        "session_token_hash": hashlib.sha256(expected_session_secret.encode()).digest(),
        "csrf_token_hash": hashlib.sha256(expected_csrf_token.encode()).digest(),
        "created_at": now,
        "last_used_at": now,
        "idle_expires_at": now + timedelta(days=7),
        "absolute_expires_at": now + timedelta(days=30),
    }
    assert expected_session_secret not in repr(issued)
    assert expected_csrf_token not in repr(issued)
    assert unit_of_work.commit_count == 1


def test_issue_rejects_non_256_bit_entropy_before_opening_unit_of_work() -> None:
    unit_of_work_opened = False

    def open_unit_of_work() -> RecordingWebSessionUnitOfWork:
        nonlocal unit_of_work_opened
        unit_of_work_opened = True
        return RecordingWebSessionUnitOfWork(RecordingWebSessionRepository())

    service = WebSessionService(
        open_unit_of_work,
        token_factory=lambda: b"too-short",
    )

    with pytest.raises(InvalidSessionSecretError):
        service.issue(
            user_id=uuid4(),
            identity_issuer="https://tenant.example.invalid/",
            identity_subject="auth0|subject-1",
        )

    assert unit_of_work_opened is False


@pytest.mark.parametrize(
    ("absolute_days_remaining", "expected_idle_days_remaining"),
    [(20, 7), (5, 5)],
    ids=["full-idle-window", "absolute-cap"],
)
def test_authenticate_returns_web_identity_and_touches_idle_with_absolute_cap(
    absolute_days_remaining: int,
    expected_idle_days_remaining: int,
) -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    active = _active_session(
        now=now,
        absolute_expires_at=now + timedelta(days=absolute_days_remaining),
    )
    repository = RecordingWebSessionRepository(active_session=active)
    unit_of_work = RecordingWebSessionUnitOfWork(repository)
    service = WebSessionService(
        lambda: unit_of_work,
        clock=lambda: now,
        idle_timeout=timedelta(days=7),
        absolute_timeout=timedelta(days=30),
    )

    resolved = service.authenticate(SESSION_SECRET)

    expected_csrf_token = derive_csrf_token(SESSION_SECRET)
    assert resolved.authenticated_user.user_id == active.user_id
    assert resolved.authenticated_user.identity_issuer == active.identity_issuer
    assert resolved.authenticated_user.identity_subject == active.identity_subject
    assert resolved.authenticated_user.session_kind is SessionKind.WEB
    assert resolved.authenticated_user.session_id == active.id
    assert resolved.csrf_token == expected_csrf_token
    assert expected_csrf_token not in repr(resolved)
    assert repository.lock_calls == [
        {
            "session_token_hash": hash_browser_secret(SESSION_SECRET),
            "now": now,
        }
    ]
    assert repository.touch_calls == [
        {
            "session_id": active.id,
            "last_used_at": now,
            "idle_expires_at": now + timedelta(days=expected_idle_days_remaining),
        }
    ]
    assert unit_of_work.commit_count == 1


@pytest.mark.parametrize(
    "malformed_secret",
    ["", "not-base64url", f"{SESSION_SECRET}=", "会" * 43, "A" * 10_000],
    ids=["empty", "short", "padded", "non-ascii", "oversized"],
)
def test_authenticate_rejects_malformed_secret_before_opening_store(
    malformed_secret: str,
) -> None:
    unit_of_work_opened = False

    def open_unit_of_work() -> RecordingWebSessionUnitOfWork:
        nonlocal unit_of_work_opened
        unit_of_work_opened = True
        return RecordingWebSessionUnitOfWork(RecordingWebSessionRepository())

    service = WebSessionService(open_unit_of_work)
    authentication_required = _expected_error_type("WebSessionAuthenticationRequiredError")

    with pytest.raises(authentication_required):
        service.authenticate(malformed_secret)

    assert unit_of_work_opened is False


def test_authenticate_rejects_unknown_canonical_session_without_touching() -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    repository = RecordingWebSessionRepository(active_session=None)
    unit_of_work = RecordingWebSessionUnitOfWork(repository)
    service = WebSessionService(lambda: unit_of_work, clock=lambda: now)
    authentication_required = _expected_error_type("WebSessionAuthenticationRequiredError")

    with pytest.raises(authentication_required):
        service.authenticate(SESSION_SECRET)

    assert repository.lock_calls == [
        {
            "session_token_hash": hash_browser_secret(SESSION_SECRET),
            "now": now,
        }
    ]
    assert repository.touch_calls == []
    assert unit_of_work.commit_count == 0


def test_authenticate_maps_session_store_failure_without_returning_identity() -> None:
    repository = RecordingWebSessionRepository(lookup_error=WebSessionPersistenceError())
    unit_of_work = RecordingWebSessionUnitOfWork(repository)
    service = WebSessionService(lambda: unit_of_work)

    with pytest.raises(WebSessionStoreUnavailableError):
        service.authenticate(SESSION_SECRET)

    assert repository.touch_calls == []
    assert unit_of_work.commit_count == 0


def test_authenticate_maps_commit_failure_without_returning_identity() -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    repository = RecordingWebSessionRepository(active_session=_active_session(now=now))
    unit_of_work = RecordingWebSessionUnitOfWork(
        repository,
        commit_error=WebSessionPersistenceError(),
    )
    service = WebSessionService(lambda: unit_of_work, clock=lambda: now)

    with pytest.raises(WebSessionStoreUnavailableError):
        service.authenticate(SESSION_SECRET)

    assert len(repository.touch_calls) == 1
    assert unit_of_work.commit_count == 1


def test_authenticate_fails_closed_when_persisted_csrf_hash_is_not_session_bound() -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    active = _active_session(now=now, csrf_token_hash=b"x" * 32)
    repository = RecordingWebSessionRepository(active_session=active)
    unit_of_work = RecordingWebSessionUnitOfWork(repository)
    service = WebSessionService(lambda: unit_of_work, clock=lambda: now)

    with pytest.raises(WebSessionStoreUnavailableError):
        service.authenticate(SESSION_SECRET)

    assert repository.touch_calls == []
    assert unit_of_work.commit_count == 0


def test_authenticate_with_csrf_validates_before_touching_session() -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    active = _active_session(now=now)
    repository = RecordingWebSessionRepository(active_session=active)
    unit_of_work = RecordingWebSessionUnitOfWork(repository)
    service = WebSessionService(lambda: unit_of_work, clock=lambda: now)
    csrf_token = derive_csrf_token(SESSION_SECRET)

    resolved = service.authenticate_with_csrf(SESSION_SECRET, csrf_token)

    assert resolved.authenticated_user.session_id == active.id
    assert repository.touch_calls == [
        {
            "session_id": active.id,
            "last_used_at": now,
            "idle_expires_at": active.absolute_expires_at,
        }
    ]
    assert unit_of_work.commit_count == 1


@pytest.mark.parametrize(
    "presented_csrf",
    [None, "not-base64url", SESSION_SECRET, derive_csrf_token(OTHER_SESSION_SECRET)],
    ids=["missing", "malformed", "session-secret", "another-session"],
)
def test_authenticate_with_csrf_failure_does_not_touch_or_commit(
    presented_csrf: str | None,
) -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    active = _active_session(now=now)
    repository = RecordingWebSessionRepository(active_session=active)
    unit_of_work = RecordingWebSessionUnitOfWork(repository)
    service = WebSessionService(lambda: unit_of_work, clock=lambda: now)
    csrf_rejected = _expected_error_type("WebSessionCsrfRejectedError")

    with pytest.raises(csrf_rejected):
        service.authenticate_with_csrf(SESSION_SECRET, presented_csrf)

    assert repository.touch_calls == []
    assert repository.revoke_calls == []
    assert unit_of_work.commit_count == 0


def test_logout_valid_session_revokes_and_commits_without_touching_idle() -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    active = _active_session(now=now)
    repository = RecordingWebSessionRepository(active_session=active)
    unit_of_work = RecordingWebSessionUnitOfWork(repository)
    service = WebSessionService(lambda: unit_of_work, clock=lambda: now)

    service.logout(SESSION_SECRET, derive_csrf_token(SESSION_SECRET))

    assert repository.touch_calls == []
    assert repository.revoke_calls == [
        {
            "session_id": active.id,
            "revoked_at": now,
        }
    ]
    assert unit_of_work.commit_count == 1


@pytest.mark.parametrize(
    "invalid_secret",
    [None, "", "not-base64url", f"{SESSION_SECRET}="],
    ids=["missing", "empty", "short", "padded"],
)
def test_logout_is_idempotent_for_missing_or_malformed_session(
    invalid_secret: str | None,
) -> None:
    repository = RecordingWebSessionRepository()
    unit_of_work = RecordingWebSessionUnitOfWork(repository)
    service = WebSessionService(lambda: unit_of_work)

    service.logout(invalid_secret, None)

    assert repository.lock_calls == []
    assert repository.touch_calls == []
    assert repository.revoke_calls == []
    assert unit_of_work.commit_count == 0


def test_logout_is_idempotent_for_unknown_or_inactive_canonical_session() -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    repository = RecordingWebSessionRepository(active_session=None)
    unit_of_work = RecordingWebSessionUnitOfWork(repository)
    service = WebSessionService(lambda: unit_of_work, clock=lambda: now)

    service.logout(SESSION_SECRET, None)

    assert repository.lock_calls == [
        {
            "session_token_hash": hash_browser_secret(SESSION_SECRET),
            "now": now,
        }
    ]
    assert repository.touch_calls == []
    assert repository.revoke_calls == []
    assert unit_of_work.commit_count == 0


@pytest.mark.parametrize(
    "presented_csrf",
    [None, "not-base64url", derive_csrf_token(OTHER_SESSION_SECRET)],
    ids=["missing", "malformed", "another-session"],
)
def test_logout_active_session_rejects_csrf_before_revoke_or_commit(
    presented_csrf: str | None,
) -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    repository = RecordingWebSessionRepository(active_session=_active_session(now=now))
    unit_of_work = RecordingWebSessionUnitOfWork(repository)
    service = WebSessionService(lambda: unit_of_work, clock=lambda: now)
    csrf_rejected = _expected_error_type("WebSessionCsrfRejectedError")

    with pytest.raises(csrf_rejected):
        service.logout(SESSION_SECRET, presented_csrf)

    assert repository.touch_calls == []
    assert repository.revoke_calls == []
    assert unit_of_work.commit_count == 0


def test_logout_maps_lookup_store_failure_without_revoke_or_commit() -> None:
    repository = RecordingWebSessionRepository(lookup_error=WebSessionPersistenceError())
    unit_of_work = RecordingWebSessionUnitOfWork(repository)
    service = WebSessionService(lambda: unit_of_work)

    with pytest.raises(WebSessionStoreUnavailableError):
        service.logout(SESSION_SECRET, derive_csrf_token(SESSION_SECRET))

    assert repository.revoke_calls == []
    assert unit_of_work.commit_count == 0


def test_logout_maps_commit_failure_to_store_unavailable() -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    active = _active_session(now=now)
    repository = RecordingWebSessionRepository(active_session=active)
    unit_of_work = RecordingWebSessionUnitOfWork(
        repository,
        commit_error=WebSessionPersistenceError(),
    )
    service = WebSessionService(lambda: unit_of_work, clock=lambda: now)

    with pytest.raises(WebSessionStoreUnavailableError):
        service.logout(SESSION_SECRET, derive_csrf_token(SESSION_SECRET))

    assert repository.revoke_calls == [{"session_id": active.id, "revoked_at": now}]
    assert unit_of_work.commit_count == 1
