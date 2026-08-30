from __future__ import annotations

import base64
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, fields
from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import UUID, uuid4

import pytest

import jobpilot_api.application.web_auth_service as web_auth_service_module
from jobpilot_api.application.identity_service import (
    AuthenticationRequiredError,
    IdentityConflictError,
    IdentityStoreUnavailableError,
    InvalidVerifiedIdentityError,
)
from jobpilot_api.application.web_auth_service import (
    InvalidWebLoginRequestError,
    WebAuthService,
    WebLoginRejectedError,
    WebLoginUnavailableError,
    WebProviderRejectedError,
    WebProviderUnavailableError,
)
from jobpilot_api.application.web_session_service import (
    WebSessionIdentityNotFoundError,
    WebSessionPersistenceError,
    WebSessionStoreUnavailableError,
)
from jobpilot_api.domain.identity import AccountStatus, LocalUser, VerifiedProviderIdentity
from jobpilot_api.domain.web_session import IssuedWebSession, LoginTransaction, WebSession

AUTHORIZE_URL = "https://tenant.example.invalid/authorize"
ISSUER = "https://tenant.example.invalid/"
SUBJECT = "auth0|web-subject"


def _opaque(value: int) -> str:
    entropy = bytes([value]) * 32
    return base64.urlsafe_b64encode(entropy).rstrip(b"=").decode("ascii")


def _digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("ascii")).digest()


def _assert_opaque_256_bit(value: str) -> None:
    assert len(value) == 43
    assert "=" not in value
    encoded = value.encode("ascii")
    padding = b"=" * (-len(encoded) % 4)
    decoded = base64.b64decode(encoded + padding, altchars=b"-_", validate=True)
    assert len(decoded) == 32


def _assert_application_rejection(
    expected_type: type[Exception],
    operation: Callable[[], object],
) -> Exception:
    with pytest.raises(expected_type) as captured:
        operation()
    assert not isinstance(captured.value, (AssertionError, AttributeError, KeyError, TypeError))
    return captured.value


def test_oversized_opaque_value_is_rejected_before_base64_decode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_decode(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("oversized untrusted input reached the Base64 decoder")

    monkeypatch.setattr(web_auth_service_module.base64, "b64decode", unexpected_decode)

    assert web_auth_service_module._is_canonical_opaque_value("A" * 10_000) is False


class DeterministicTokenFactory:
    def __init__(self) -> None:
        self._values = [bytes([value]) * 32 for value in range(1, 5)]
        self.call_count = 0

    def __call__(self) -> bytes:
        if self.call_count >= len(self._values):
            raise AssertionError("Web auth start requested more than four opaque values")
        value = self._values[self.call_count]
        self.call_count += 1
        return value


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class RecordingLoginTransactionRepository:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self.create_call: dict[str, object] | None = None
        self.delete_expired_calls: list[datetime] = []
        self.consume_calls: list[dict[str, object]] = []
        self.transaction: LoginTransaction | None = None
        self.consumed = False

    def delete_expired(self, *, now: datetime) -> None:
        self.delete_expired_calls.append(now)

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
    ) -> LoginTransaction:
        self._events.append("transaction_create")
        self.create_call = {
            "browser_handle_hash": browser_handle_hash,
            "state_hash": state_hash,
            "nonce_hash": nonce_hash,
            "pkce_verifier": pkce_verifier,
            "intent": intent,
            "return_to": return_to,
            "created_at": created_at,
            "expires_at": expires_at,
        }
        self.transaction = LoginTransaction(id=uuid4(), **self.create_call)  # type: ignore[arg-type]
        return self.transaction

    def consume(
        self,
        *,
        browser_handle_hash: bytes | None,
        state_hash: bytes | None,
        now: datetime,
    ) -> LoginTransaction | None:
        self._events.append("transaction_consume")
        self.consume_calls.append(
            {
                "browser_handle_hash": browser_handle_hash,
                "state_hash": state_hash,
                "now": now,
            }
        )
        transaction = self.transaction
        if transaction is None or self.consumed:
            return None

        handle_identifies = (
            browser_handle_hash is not None
            and browser_handle_hash == transaction.browser_handle_hash
        )
        state_identifies = state_hash is not None and state_hash == transaction.state_hash
        if not handle_identifies and not state_identifies:
            return None

        self.consumed = True
        if (
            browser_handle_hash == transaction.browser_handle_hash
            and state_hash == transaction.state_hash
            and now < transaction.expires_at
        ):
            return transaction
        return None


class RecordingWebAuthUnitOfWork:
    def __init__(
        self,
        repository: RecordingLoginTransactionRepository,
        events: list[str],
    ) -> None:
        self.sessions = object()
        self.login_transactions = repository
        self._events = events
        self.commit_count = 0
        self.commit_error: Exception | None = None

    def __enter__(self) -> RecordingWebAuthUnitOfWork:
        self._events.append("uow_enter")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._events.append("uow_exit")

    def commit(self) -> None:
        self._events.append("uow_commit")
        self.commit_count += 1
        if self.commit_error is not None:
            raise self.commit_error


class RecordingProvider:
    def __init__(self, identity: VerifiedProviderIdentity, events: list[str]) -> None:
        self._identity = identity
        self._events = events
        self.raw_provider_token = "provider-access-token-must-not-cross-the-boundary"
        self.authorization_calls: list[dict[str, str]] = []
        self.exchange_calls: list[dict[str, object]] = []
        self.exchange_error: Exception | None = None

    def authorization_url(
        self,
        *,
        intent: str,
        state: str,
        nonce: str,
        pkce_verifier: str,
    ) -> str:
        self._events.append("provider_authorization_url")
        self.authorization_calls.append(
            {
                "intent": intent,
                "state": state,
                "nonce": nonce,
                "pkce_verifier": pkce_verifier,
            }
        )
        return AUTHORIZE_URL

    def exchange_code(
        self,
        *,
        code: str,
        pkce_verifier: str,
        expected_nonce_hash: bytes,
    ) -> VerifiedProviderIdentity:
        self._events.append("provider_exchange")
        self.exchange_calls.append(
            {
                "code": code,
                "pkce_verifier": pkce_verifier,
                "expected_nonce_hash": expected_nonce_hash,
            }
        )
        if self.exchange_error is not None:
            raise self.exchange_error
        return self._identity


class RecordingIdentityService:
    def __init__(self, user: LocalUser, events: list[str]) -> None:
        self._user = user
        self._events = events
        self.provision_calls: list[VerifiedProviderIdentity] = []
        self.provision_error: Exception | None = None

    def provision(self, identity: VerifiedProviderIdentity) -> LocalUser:
        self._events.append("identity_provision")
        self.provision_calls.append(identity)
        if self.provision_error is not None:
            raise self.provision_error
        return self._user


class RecordingWebSessionService:
    def __init__(self, issued_session: IssuedWebSession, events: list[str]) -> None:
        self._issued_session = issued_session
        self._events = events
        self.issue_calls: list[dict[str, object]] = []
        self.issue_error: Exception | None = None

    def issue(
        self,
        *,
        user_id: UUID,
        identity_issuer: str,
        identity_subject: str,
    ) -> IssuedWebSession:
        self._events.append("session_issue")
        self.issue_calls.append(
            {
                "user_id": user_id,
                "identity_issuer": identity_issuer,
                "identity_subject": identity_subject,
            }
        )
        if self.issue_error is not None:
            raise self.issue_error
        return self._issued_session


@dataclass(slots=True)
class Scenario:
    service: WebAuthService
    clock: MutableClock
    token_factory: DeterministicTokenFactory
    repository: RecordingLoginTransactionRepository
    unit_of_work: RecordingWebAuthUnitOfWork
    provider: RecordingProvider
    identity_service: RecordingIdentityService
    web_session_service: RecordingWebSessionService
    identity: VerifiedProviderIdentity
    user: LocalUser
    issued_session: IssuedWebSession
    events: list[str]


def _scenario(
    *,
    allowed_return_paths: frozenset[str] = frozenset({"/"}),
) -> Scenario:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    events: list[str] = []
    clock = MutableClock(now)
    token_factory = DeterministicTokenFactory()
    repository = RecordingLoginTransactionRepository(events)
    unit_of_work = RecordingWebAuthUnitOfWork(repository, events)
    identity = VerifiedProviderIdentity(
        issuer=ISSUER,
        subject=SUBJECT,
        verified_email="person@example.com",
        authorized_party="web-client-id",
    )
    user = LocalUser(
        id=uuid4(),
        email=identity.verified_email,
        display_name=None,
        locale=None,
        time_zone=None,
        account_status=AccountStatus.ACTIVE,
        deletion_requested_at=None,
        created_at=now,
        updated_at=now,
    )
    web_session = WebSession(
        id=uuid4(),
        user_id=user.id,
        identity_issuer=identity.issuer,
        identity_subject=identity.subject,
        csrf_token_hash=b"c" * 32,
        created_at=now,
        last_used_at=now,
        idle_expires_at=now + timedelta(days=7),
        absolute_expires_at=now + timedelta(days=30),
        revoked_at=None,
    )
    issued_session = IssuedWebSession(
        session=web_session,
        session_secret="opaque-session-secret",
        csrf_token="session-bound-csrf-token",
    )
    provider = RecordingProvider(identity, events)
    identity_service = RecordingIdentityService(user, events)
    web_session_service = RecordingWebSessionService(issued_session, events)
    service = WebAuthService(
        lambda: unit_of_work,
        identity_service,
        web_session_service,
        provider,
        token_factory=token_factory,
        clock=clock,
        allowed_return_paths=allowed_return_paths,
    )
    return Scenario(
        service=service,
        clock=clock,
        token_factory=token_factory,
        repository=repository,
        unit_of_work=unit_of_work,
        provider=provider,
        identity_service=identity_service,
        web_session_service=web_session_service,
        identity=identity,
        user=user,
        issued_session=issued_session,
        events=events,
    )


def test_begin_uses_four_independent_256_bit_values_and_persists_only_hashes() -> None:
    scenario = _scenario(allowed_return_paths=frozenset({"/", "/jobs"}))

    started = scenario.service.begin(intent="login", return_to="/jobs")

    assert tuple(field.name for field in fields(started)) == (
        "authorization_url",
        "browser_handle",
        "transaction_max_age",
    )
    assert type(started).__name__ == "WebLoginStart"
    assert started.authorization_url == AUTHORIZE_URL
    assert 0 < started.transaction_max_age <= 600
    assert scenario.token_factory.call_count == 4
    assert scenario.unit_of_work.commit_count == 1
    assert scenario.repository.delete_expired_calls == [scenario.clock.now]

    authorization = scenario.provider.authorization_calls[0]
    browser_handle = started.browser_handle
    state = authorization["state"]
    nonce = authorization["nonce"]
    pkce_verifier = authorization["pkce_verifier"]
    opaque_values = (browser_handle, state, nonce, pkce_verifier)
    assert len(set(opaque_values)) == 4
    for opaque_value in opaque_values:
        _assert_opaque_256_bit(opaque_value)

    assert scenario.repository.create_call == {
        "browser_handle_hash": _digest(browser_handle),
        "state_hash": _digest(state),
        "nonce_hash": _digest(nonce),
        "pkce_verifier": pkce_verifier,
        "intent": "login",
        "return_to": "/jobs",
        "created_at": scenario.clock.now,
        "expires_at": scenario.clock.now + timedelta(seconds=started.transaction_max_age),
    }
    assert browser_handle not in repr(scenario.repository.create_call)
    assert state not in repr(scenario.repository.create_call)
    assert nonce not in repr(scenario.repository.create_call)


@pytest.mark.parametrize("intent", ["login", "signup"])
def test_begin_accepts_only_the_two_frozen_intents(intent: str) -> None:
    scenario = _scenario()

    scenario.service.begin(intent=intent, return_to=None)

    assert scenario.repository.create_call is not None
    assert scenario.repository.create_call["intent"] == intent
    assert scenario.provider.authorization_calls[0]["intent"] == intent


@pytest.mark.parametrize("intent", ["", "LOGIN", "reauth", "logout"])
def test_begin_rejects_any_intent_outside_login_and_signup(intent: str) -> None:
    scenario = _scenario()

    _assert_application_rejection(
        InvalidWebLoginRequestError,
        lambda: scenario.service.begin(intent=intent, return_to=None),
    )

    assert scenario.repository.create_call is None
    assert scenario.provider.authorization_calls == []
    assert scenario.unit_of_work.commit_count == 0


@pytest.mark.parametrize(
    ("return_to", "expected"),
    [(None, "/"), ("/jobs", "/jobs")],
)
def test_begin_defaults_to_root_and_accepts_an_exact_allowlisted_relative_path(
    return_to: str | None,
    expected: str,
) -> None:
    scenario = _scenario(allowed_return_paths=frozenset({"/", "/jobs"}))

    scenario.service.begin(intent="login", return_to=return_to)

    assert scenario.repository.create_call is not None
    assert scenario.repository.create_call["return_to"] == expected


@pytest.mark.parametrize(
    "return_to",
    [
        "https://evil.example/",
        "//evil.example/",
        "/jobs/",
        "/jobs?next=/",
        "/jobs#details",
        "/admin",
        " jobs",
    ],
)
def test_begin_rejects_non_relative_or_non_exact_return_paths(return_to: str) -> None:
    scenario = _scenario(allowed_return_paths=frozenset({"/", "/jobs"}))

    _assert_application_rejection(
        InvalidWebLoginRequestError,
        lambda: scenario.service.begin(intent="login", return_to=return_to),
    )

    assert scenario.repository.create_call is None
    assert scenario.provider.authorization_calls == []
    assert scenario.unit_of_work.commit_count == 0


def test_complete_commits_one_time_consumption_before_provider_exchange_and_issues_session() -> (
    None
):
    scenario = _scenario(allowed_return_paths=frozenset({"/", "/jobs"}))
    started = scenario.service.begin(intent="signup", return_to="/jobs")
    authorization = scenario.provider.authorization_calls[0]
    scenario.events.clear()

    completed = scenario.service.complete(
        browser_handle=started.browser_handle,
        state=authorization["state"],
        code="provider-authorization-code",
    )

    assert scenario.events == [
        "uow_enter",
        "transaction_consume",
        "uow_commit",
        "uow_exit",
        "provider_exchange",
        "identity_provision",
        "session_issue",
    ]
    assert scenario.repository.consume_calls[-1] == {
        "browser_handle_hash": _digest(started.browser_handle),
        "state_hash": _digest(authorization["state"]),
        "now": scenario.clock.now,
    }
    assert scenario.provider.exchange_calls == [
        {
            "code": "provider-authorization-code",
            "pkce_verifier": authorization["pkce_verifier"],
            "expected_nonce_hash": _digest(authorization["nonce"]),
        }
    ]
    assert scenario.identity_service.provision_calls == [scenario.identity]
    assert scenario.web_session_service.issue_calls == [
        {
            "user_id": scenario.user.id,
            "identity_issuer": scenario.identity.issuer,
            "identity_subject": scenario.identity.subject,
        }
    ]
    assert type(completed).__name__ == "WebLoginCompletion"
    assert tuple(field.name for field in fields(completed)) == (
        "user",
        "issued_session",
        "return_to",
    )
    assert completed.user is scenario.user
    assert completed.issued_session is scenario.issued_session
    assert completed.return_to == "/jobs"
    assert scenario.provider.raw_provider_token not in repr(completed)


@pytest.mark.parametrize(
    "case",
    ["missing-browser-handle", "missing-state", "mismatch", "expired"],
)
def test_complete_missing_mismatched_or_expired_transaction_fails_closed(case: str) -> None:
    scenario = _scenario()
    started = scenario.service.begin(intent="login", return_to=None)
    state = scenario.provider.authorization_calls[0]["state"]
    browser_handle: str | None = started.browser_handle
    callback_state: str | None = state
    if case == "missing-browser-handle":
        browser_handle = None
    elif case == "missing-state":
        callback_state = None
    elif case == "mismatch":
        callback_state = _opaque(99)
    elif case == "expired":
        scenario.clock.now += timedelta(seconds=601)
    scenario.events.clear()
    commits_before = scenario.unit_of_work.commit_count

    rejection = _assert_application_rejection(
        WebLoginRejectedError,
        lambda: scenario.service.complete(
            browser_handle=browser_handle,
            state=callback_state,
            code="provider-authorization-code",
        ),
    )

    assert scenario.events == [
        "uow_enter",
        "transaction_consume",
        "uow_commit",
        "uow_exit",
    ]
    assert scenario.unit_of_work.commit_count == commits_before + 1
    assert scenario.repository.consumed
    assert scenario.provider.exchange_calls == []
    assert scenario.identity_service.provision_calls == []
    assert scenario.web_session_service.issue_calls == []
    for untrusted_value in (browser_handle, callback_state):
        if untrusted_value is not None:
            assert untrusted_value not in repr(rejection)


@pytest.mark.parametrize(
    ("provider_error", "code"),
    [(True, "ignored-provider-code"), (False, None)],
    ids=["provider-error", "missing-code"],
)
def test_complete_provider_error_or_missing_code_consumes_transaction_without_exchange(
    provider_error: bool,
    code: str | None,
) -> None:
    scenario = _scenario()
    started = scenario.service.begin(intent="login", return_to=None)
    state = scenario.provider.authorization_calls[0]["state"]
    scenario.events.clear()
    commits_before = scenario.unit_of_work.commit_count

    _assert_application_rejection(
        WebLoginRejectedError,
        lambda: scenario.service.complete(
            browser_handle=started.browser_handle,
            state=state,
            code=code,
            provider_error=provider_error,
        ),
    )

    assert scenario.events == [
        "uow_enter",
        "transaction_consume",
        "uow_commit",
        "uow_exit",
    ]
    assert scenario.unit_of_work.commit_count == commits_before + 1
    assert scenario.repository.consumed
    assert scenario.provider.exchange_calls == []
    assert scenario.identity_service.provision_calls == []
    assert scenario.web_session_service.issue_calls == []


def test_complete_replay_fails_after_the_first_callback_consumes_the_transaction() -> None:
    scenario = _scenario()
    started = scenario.service.begin(intent="login", return_to=None)
    state = scenario.provider.authorization_calls[0]["state"]
    scenario.service.complete(
        browser_handle=started.browser_handle,
        state=state,
        code="first-provider-code",
    )
    scenario.events.clear()
    commits_before = scenario.unit_of_work.commit_count

    _assert_application_rejection(
        WebLoginRejectedError,
        lambda: scenario.service.complete(
            browser_handle=started.browser_handle,
            state=state,
            code="replayed-provider-code",
        ),
    )

    assert scenario.events == [
        "uow_enter",
        "transaction_consume",
        "uow_commit",
        "uow_exit",
    ]
    assert scenario.unit_of_work.commit_count == commits_before + 1
    assert len(scenario.provider.exchange_calls) == 1
    assert len(scenario.identity_service.provision_calls) == 1
    assert len(scenario.web_session_service.issue_calls) == 1


def test_begin_maps_login_transaction_store_failure_to_unavailable() -> None:
    scenario = _scenario()
    scenario.unit_of_work.commit_error = WebSessionPersistenceError()

    _assert_application_rejection(
        WebLoginUnavailableError,
        lambda: scenario.service.begin(intent="login", return_to=None),
    )

    assert scenario.provider.authorization_calls
    assert scenario.repository.create_call is not None


def test_complete_maps_login_transaction_store_failure_to_unavailable() -> None:
    scenario = _scenario()
    started = scenario.service.begin(intent="login", return_to=None)
    state = scenario.provider.authorization_calls[0]["state"]
    scenario.unit_of_work.commit_error = WebSessionPersistenceError()

    _assert_application_rejection(
        WebLoginUnavailableError,
        lambda: scenario.service.complete(
            browser_handle=started.browser_handle,
            state=state,
            code="provider-authorization-code",
        ),
    )

    assert scenario.provider.exchange_calls == []
    assert scenario.identity_service.provision_calls == []
    assert scenario.web_session_service.issue_calls == []


@pytest.mark.parametrize(
    ("error", "expected_type"),
    [
        (WebProviderRejectedError(), WebLoginRejectedError),
        (WebProviderUnavailableError(), WebLoginUnavailableError),
    ],
    ids=["provider-rejected", "provider-unavailable"],
)
def test_complete_maps_provider_failures_to_application_errors(
    error: Exception,
    expected_type: type[Exception],
) -> None:
    scenario = _scenario()
    started = scenario.service.begin(intent="login", return_to=None)
    state = scenario.provider.authorization_calls[0]["state"]
    scenario.provider.exchange_error = error

    _assert_application_rejection(
        expected_type,
        lambda: scenario.service.complete(
            browser_handle=started.browser_handle,
            state=state,
            code="provider-authorization-code",
        ),
    )

    assert scenario.repository.consumed
    assert scenario.identity_service.provision_calls == []
    assert scenario.web_session_service.issue_calls == []


@pytest.mark.parametrize(
    ("error", "expected_type"),
    [
        (AuthenticationRequiredError(), WebLoginRejectedError),
        (IdentityConflictError(), WebLoginRejectedError),
        (InvalidVerifiedIdentityError(), WebLoginRejectedError),
        (IdentityStoreUnavailableError(), WebLoginUnavailableError),
    ],
    ids=[
        "account-not-active",
        "identity-conflict",
        "invalid-identity",
        "identity-store-unavailable",
    ],
)
def test_complete_maps_identity_failures_to_application_errors(
    error: Exception,
    expected_type: type[Exception],
) -> None:
    scenario = _scenario()
    started = scenario.service.begin(intent="login", return_to=None)
    state = scenario.provider.authorization_calls[0]["state"]
    scenario.identity_service.provision_error = error

    _assert_application_rejection(
        expected_type,
        lambda: scenario.service.complete(
            browser_handle=started.browser_handle,
            state=state,
            code="provider-authorization-code",
        ),
    )

    assert scenario.repository.consumed
    assert scenario.web_session_service.issue_calls == []


@pytest.mark.parametrize(
    ("error", "expected_type"),
    [
        (WebSessionIdentityNotFoundError(), WebLoginRejectedError),
        (WebSessionStoreUnavailableError(), WebLoginUnavailableError),
    ],
    ids=["identity-disappeared", "session-store-unavailable"],
)
def test_complete_maps_session_failures_to_application_errors(
    error: Exception,
    expected_type: type[Exception],
) -> None:
    scenario = _scenario()
    started = scenario.service.begin(intent="login", return_to=None)
    state = scenario.provider.authorization_calls[0]["state"]
    scenario.web_session_service.issue_error = error

    _assert_application_rejection(
        expected_type,
        lambda: scenario.service.complete(
            browser_handle=started.browser_handle,
            state=state,
            code="provider-authorization-code",
        ),
    )

    assert scenario.repository.consumed
    assert scenario.identity_service.provision_calls


def test_complete_does_not_hide_an_unexpected_programming_error() -> None:
    scenario = _scenario()
    started = scenario.service.begin(intent="login", return_to=None)
    state = scenario.provider.authorization_calls[0]["state"]
    scenario.provider.exchange_error = RuntimeError("programming defect")

    with pytest.raises(RuntimeError, match="programming defect"):
        scenario.service.complete(
            browser_handle=started.browser_handle,
            state=state,
            code="provider-authorization-code",
        )

    assert scenario.repository.consumed
    assert scenario.identity_service.provision_calls == []
    assert scenario.web_session_service.issue_calls == []
