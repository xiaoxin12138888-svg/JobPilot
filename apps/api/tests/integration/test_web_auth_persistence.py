from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from jobpilot_api.application.identity_service import IdentityService
from jobpilot_api.application.web_session_service import (
    WebSessionIdentityNotFoundError,
    WebSessionService,
    hash_browser_secret,
)
from jobpilot_api.domain.identity import VerifiedProviderIdentity
from jobpilot_api.infrastructure.database.identity_repository import SqlAlchemyIdentityUnitOfWork
from jobpilot_api.infrastructure.database.models import (
    IdentityRecord,
    LoginTransactionRecord,
    UserRecord,
    WebSessionRecord,
)
from jobpilot_api.infrastructure.database.web_session_repository import (
    LOGIN_TRANSACTION_PRUNE_BATCH,
    SqlAlchemyWebSessionUnitOfWork,
)

ISSUER = "https://tenant.example.invalid/"
SUBJECT = "auth0|web-subject"
SESSION_SECRET = "session-secret-that-is-never-persisted"
CSRF_TOKEN = "derived-session-bound-csrf-token"


def _digest(value: str) -> bytes:
    return hashlib.sha256(value.encode()).digest()


def _create_user_and_identity(
    engine: Engine,
    *,
    subject: str = SUBJECT,
    email: str = "person@example.com",
) -> UUID:
    identity_service = IdentityService(lambda: SqlAlchemyIdentityUnitOfWork(engine))
    user = identity_service.provision(
        VerifiedProviderIdentity(
            issuer=ISSUER,
            subject=subject,
            verified_email=email,
            authorized_party="web-client-id",
        )
    )
    with Session(engine) as session:
        identity_id = session.scalar(
            select(IdentityRecord.id).where(
                IdentityRecord.user_id == user.id,
                IdentityRecord.issuer == ISSUER,
                IdentityRecord.subject == subject,
            )
        )
    assert identity_id is not None
    return user.id


def _create_session(
    engine: Engine,
    *,
    session_secret: str = SESSION_SECRET,
    created_at: datetime,
    idle_expires_at: datetime,
    absolute_expires_at: datetime,
) -> UUID:
    user_id = _create_user_and_identity(engine)
    with SqlAlchemyWebSessionUnitOfWork(engine) as unit_of_work:
        created = unit_of_work.sessions.create(
            user_id=user_id,
            identity_issuer=ISSUER,
            identity_subject=SUBJECT,
            session_token_hash=_digest(session_secret),
            csrf_token_hash=_digest(CSRF_TOKEN),
            created_at=created_at,
            last_used_at=created_at,
            idle_expires_at=idle_expires_at,
            absolute_expires_at=absolute_expires_at,
        )
        unit_of_work.commit()
        return created.id


@pytest.mark.parametrize("use_another_users_identity", [False, True])
def test_web_session_creation_rejects_unknown_or_mismatched_identity(
    migrated_engine: Engine,
    use_another_users_identity: bool,
) -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    user_id = _create_user_and_identity(migrated_engine)
    identity_subject = "auth0|unknown"
    if use_another_users_identity:
        _create_user_and_identity(
            migrated_engine,
            subject="auth0|another-user",
            email="another@example.com",
        )
        identity_subject = "auth0|another-user"

    with pytest.raises(WebSessionIdentityNotFoundError):
        with SqlAlchemyWebSessionUnitOfWork(migrated_engine) as unit_of_work:
            unit_of_work.sessions.create(
                user_id=user_id,
                identity_issuer=ISSUER,
                identity_subject=identity_subject,
                session_token_hash=_digest(SESSION_SECRET),
                csrf_token_hash=_digest(CSRF_TOKEN),
                created_at=now,
                last_used_at=now,
                idle_expires_at=now + timedelta(days=7),
                absolute_expires_at=now + timedelta(days=30),
            )
            unit_of_work.commit()

    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(WebSessionRecord)) == 0


def test_web_session_persists_only_hashes_of_browser_secrets(
    migrated_engine: Engine,
) -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)

    session_id = _create_session(
        migrated_engine,
        created_at=now,
        idle_expires_at=now + timedelta(days=7),
        absolute_expires_at=now + timedelta(days=30),
    )

    with Session(migrated_engine) as session:
        stored = session.get(WebSessionRecord, session_id)
        assert stored is not None
        assert stored.session_token_hash == _digest(SESSION_SECRET)
        assert stored.csrf_token_hash == _digest(CSRF_TOKEN)
        assert len(stored.session_token_hash) == 32
        assert len(stored.csrf_token_hash) == 32
        assert not hasattr(stored, "session_token")
        assert not hasattr(stored, "csrf_token")


def test_web_session_service_keeps_issued_secrets_out_of_persistence(
    migrated_engine: Engine,
) -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    user_id = _create_user_and_identity(migrated_engine)
    service = WebSessionService(
        lambda: SqlAlchemyWebSessionUnitOfWork(migrated_engine),
        token_factory=lambda: bytes(range(32)),
        clock=lambda: now,
    )

    issued = service.issue(
        user_id=user_id,
        identity_issuer=ISSUER,
        identity_subject=SUBJECT,
    )

    with Session(migrated_engine) as session:
        stored = session.get(WebSessionRecord, issued.session.id)
        assert stored is not None
        assert stored.session_token_hash == hash_browser_secret(issued.session_secret)
        assert stored.csrf_token_hash == hash_browser_secret(issued.csrf_token)
        assert issued.session_secret.encode() not in {
            stored.session_token_hash,
            stored.csrf_token_hash,
        }
        assert issued.csrf_token.encode() not in {
            stored.session_token_hash,
            stored.csrf_token_hash,
        }


def test_active_web_session_resolves_the_bound_local_identity(
    migrated_engine: Engine,
) -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    session_id = _create_session(
        migrated_engine,
        created_at=now,
        idle_expires_at=now + timedelta(days=7),
        absolute_expires_at=now + timedelta(days=30),
    )

    with SqlAlchemyWebSessionUnitOfWork(migrated_engine) as unit_of_work:
        active = unit_of_work.sessions.find_active_by_token_hash(
            _digest(SESSION_SECRET),
            now=now + timedelta(days=1),
        )

    assert active is not None
    assert active.id == session_id
    assert active.identity_issuer == ISSUER
    assert active.identity_subject == SUBJECT
    assert active.revoked_at is None


@pytest.mark.parametrize(
    ("created_at", "idle_expires_at", "absolute_expires_at"),
    [
        (
            datetime(2026, 8, 22, 9, 0, tzinfo=UTC),
            datetime(2026, 8, 30, 8, 59, tzinfo=UTC),
            datetime(2026, 9, 21, 9, 0, tzinfo=UTC),
        ),
        (
            datetime(2026, 7, 30, 9, 0, tzinfo=UTC),
            datetime(2026, 8, 30, 8, 58, tzinfo=UTC),
            datetime(2026, 8, 30, 8, 59, tzinfo=UTC),
        ),
    ],
    ids=["idle-expired", "absolute-and-idle-expired"],
)
def test_expired_web_session_fails_closed(
    migrated_engine: Engine,
    created_at: datetime,
    idle_expires_at: datetime,
    absolute_expires_at: datetime,
) -> None:
    lookup_time = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    _create_session(
        migrated_engine,
        created_at=created_at,
        idle_expires_at=idle_expires_at,
        absolute_expires_at=absolute_expires_at,
    )

    with SqlAlchemyWebSessionUnitOfWork(migrated_engine) as unit_of_work:
        active = unit_of_work.sessions.find_active_by_token_hash(
            _digest(SESSION_SECRET),
            now=lookup_time,
        )

    assert active is None


def test_revoked_web_session_fails_closed(migrated_engine: Engine) -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    session_id = _create_session(
        migrated_engine,
        created_at=now,
        idle_expires_at=now + timedelta(days=7),
        absolute_expires_at=now + timedelta(days=30),
    )
    revoked_at = now + timedelta(minutes=5)
    with SqlAlchemyWebSessionUnitOfWork(migrated_engine) as unit_of_work:
        unit_of_work.sessions.revoke(session_id, revoked_at=revoked_at)
        unit_of_work.commit()

    with SqlAlchemyWebSessionUnitOfWork(migrated_engine) as unit_of_work:
        active = unit_of_work.sessions.find_active_by_token_hash(
            _digest(SESSION_SECRET),
            now=revoked_at,
        )

    assert active is None
    with Session(migrated_engine) as session:
        stored = session.get(WebSessionRecord, session_id)
        assert stored is not None
        assert stored.revoked_at == revoked_at


def test_unknown_web_session_hash_fails_closed(migrated_engine: Engine) -> None:
    with SqlAlchemyWebSessionUnitOfWork(migrated_engine) as unit_of_work:
        active = unit_of_work.sessions.find_active_by_token_hash(
            _digest("unknown-session-secret"),
            now=datetime(2026, 8, 30, 9, 0, tzinfo=UTC),
        )

    assert active is None


def test_deletion_pending_user_session_fails_closed(migrated_engine: Engine) -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    session_id = _create_session(
        migrated_engine,
        created_at=now,
        idle_expires_at=now + timedelta(days=7),
        absolute_expires_at=now + timedelta(days=30),
    )
    with Session(migrated_engine) as session, session.begin():
        stored_session = session.get(WebSessionRecord, session_id)
        assert stored_session is not None
        user = session.get(UserRecord, stored_session.user_id)
        assert user is not None
        user.account_status = "deletion_pending"
        user.deletion_requested_at = now + timedelta(minutes=1)

    with SqlAlchemyWebSessionUnitOfWork(migrated_engine) as unit_of_work:
        active = unit_of_work.sessions.find_active_by_token_hash(
            _digest(SESSION_SECRET),
            now=now + timedelta(minutes=2),
        )

    assert active is None


def _create_login_transaction(
    engine: Engine,
    *,
    browser_handle: str,
    state: str,
    created_at: datetime,
    expires_at: datetime,
) -> UUID:
    with SqlAlchemyWebSessionUnitOfWork(engine) as unit_of_work:
        created = unit_of_work.login_transactions.create(
            browser_handle_hash=_digest(browser_handle),
            state_hash=_digest(state),
            nonce_hash=_digest("nonce-for-" + state),
            pkce_verifier="v" * 64,
            intent="login",
            return_to="/",
            created_at=created_at,
            expires_at=expires_at,
        )
        unit_of_work.commit()
        return created.id


def test_login_transaction_is_consumed_once_and_replay_fails_closed(
    migrated_engine: Engine,
) -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    transaction_id = _create_login_transaction(
        migrated_engine,
        browser_handle="browser-handle",
        state="oauth-state",
        created_at=now,
        expires_at=now + timedelta(minutes=10),
    )

    with SqlAlchemyWebSessionUnitOfWork(migrated_engine) as unit_of_work:
        consumed = unit_of_work.login_transactions.consume(
            browser_handle_hash=_digest("browser-handle"),
            state_hash=_digest("oauth-state"),
            now=now + timedelta(minutes=1),
        )
        unit_of_work.commit()

    assert consumed is not None
    assert consumed.id == transaction_id
    assert consumed.pkce_verifier == "v" * 64

    with SqlAlchemyWebSessionUnitOfWork(migrated_engine) as unit_of_work:
        replayed = unit_of_work.login_transactions.consume(
            browser_handle_hash=_digest("browser-handle"),
            state_hash=_digest("oauth-state"),
            now=now + timedelta(minutes=1),
        )
        unit_of_work.commit()

    assert replayed is None
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(LoginTransactionRecord)) == 0


def test_expired_abandoned_login_transactions_are_pruned_without_deleting_live_ones(
    migrated_engine: Engine,
) -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    expired_id = _create_login_transaction(
        migrated_engine,
        browser_handle="expired-browser-handle",
        state="expired-state",
        created_at=now - timedelta(minutes=10),
        expires_at=now,
    )
    live_id = _create_login_transaction(
        migrated_engine,
        browser_handle="live-browser-handle",
        state="live-state",
        created_at=now,
        expires_at=now + timedelta(minutes=10),
    )

    with SqlAlchemyWebSessionUnitOfWork(migrated_engine) as unit_of_work:
        unit_of_work.login_transactions.delete_expired(now=now)
        unit_of_work.commit()

    with Session(migrated_engine) as session:
        assert session.get(LoginTransactionRecord, expired_id) is None
        assert session.get(LoginTransactionRecord, live_id) is not None


def test_expired_login_transaction_pruning_is_bounded_per_authorize_attempt(
    migrated_engine: Engine,
) -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    with SqlAlchemyWebSessionUnitOfWork(migrated_engine) as unit_of_work:
        for index in range(LOGIN_TRANSACTION_PRUNE_BATCH + 1):
            unit_of_work.login_transactions.create(
                browser_handle_hash=_digest(f"expired-browser-{index}"),
                state_hash=_digest(f"expired-state-{index}"),
                nonce_hash=_digest(f"expired-nonce-{index}"),
                pkce_verifier="v" * 64,
                intent="login",
                return_to="/",
                created_at=now - timedelta(minutes=10),
                expires_at=now,
            )
        unit_of_work.commit()

    with SqlAlchemyWebSessionUnitOfWork(migrated_engine) as unit_of_work:
        unit_of_work.login_transactions.delete_expired(now=now)
        unit_of_work.commit()

    with Session(migrated_engine) as session:
        remaining = session.scalar(select(func.count()).select_from(LoginTransactionRecord))
        assert remaining == 1


def test_concurrent_login_transaction_consumers_release_verifier_once(
    migrated_engine: Engine,
) -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    _create_login_transaction(
        migrated_engine,
        browser_handle="concurrent-browser",
        state="concurrent-state",
        created_at=now,
        expires_at=now + timedelta(minutes=10),
    )
    start = Barrier(2)

    def consume() -> str | None:
        start.wait(timeout=5)
        with SqlAlchemyWebSessionUnitOfWork(migrated_engine) as unit_of_work:
            transaction = unit_of_work.login_transactions.consume(
                browser_handle_hash=_digest("concurrent-browser"),
                state_hash=_digest("concurrent-state"),
                now=now + timedelta(minutes=1),
            )
            unit_of_work.commit()
            return transaction.pkce_verifier if transaction is not None else None

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = [future.result() for future in [executor.submit(consume) for _ in range(2)]]

    assert outcomes.count("v" * 64) == 1
    assert outcomes.count(None) == 1
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(LoginTransactionRecord)) == 0


@pytest.mark.parametrize(
    ("browser_handle_hash", "state_hash"),
    [
        (None, _digest("one-sided-state")),
        (_digest("one-sided-browser"), None),
    ],
    ids=["missing-browser-handle", "missing-state"],
)
def test_incomplete_login_transaction_callback_deletes_the_identifiable_record(
    migrated_engine: Engine,
    browser_handle_hash: bytes | None,
    state_hash: bytes | None,
) -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    _create_login_transaction(
        migrated_engine,
        browser_handle="one-sided-browser",
        state="one-sided-state",
        created_at=now,
        expires_at=now + timedelta(minutes=10),
    )

    with SqlAlchemyWebSessionUnitOfWork(migrated_engine) as unit_of_work:
        consumed = unit_of_work.login_transactions.consume(
            browser_handle_hash=browser_handle_hash,
            state_hash=state_hash,
            now=now + timedelta(minutes=1),
        )
        unit_of_work.commit()

    assert consumed is None
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(LoginTransactionRecord)) == 0


def test_login_transaction_mismatch_deletes_every_identifiable_record(
    migrated_engine: Engine,
) -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    _create_login_transaction(
        migrated_engine,
        browser_handle="browser-a",
        state="state-a",
        created_at=now,
        expires_at=now + timedelta(minutes=10),
    )
    _create_login_transaction(
        migrated_engine,
        browser_handle="browser-b",
        state="state-b",
        created_at=now,
        expires_at=now + timedelta(minutes=10),
    )

    with SqlAlchemyWebSessionUnitOfWork(migrated_engine) as unit_of_work:
        consumed = unit_of_work.login_transactions.consume(
            browser_handle_hash=_digest("browser-a"),
            state_hash=_digest("state-b"),
            now=now + timedelta(minutes=1),
        )
        unit_of_work.commit()

    assert consumed is None
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(LoginTransactionRecord)) == 0


def test_expired_login_transaction_is_deleted_without_being_returned(
    migrated_engine: Engine,
) -> None:
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    _create_login_transaction(
        migrated_engine,
        browser_handle="expired-browser",
        state="expired-state",
        created_at=now - timedelta(minutes=11),
        expires_at=now - timedelta(minutes=1),
    )

    with SqlAlchemyWebSessionUnitOfWork(migrated_engine) as unit_of_work:
        consumed = unit_of_work.login_transactions.consume(
            browser_handle_hash=_digest("expired-browser"),
            state_hash=_digest("expired-state"),
            now=now,
        )
        unit_of_work.commit()

    assert consumed is None
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(LoginTransactionRecord)) == 0
