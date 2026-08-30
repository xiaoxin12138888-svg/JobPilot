from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier, Lock
from types import TracebackType
from uuid import UUID

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from jobpilot_api.application.identity_service import (
    AuthenticationRequiredError,
    IdentityConflictError,
    IdentityRepository,
    IdentityService,
)
from jobpilot_api.domain.identity import LocalUser, VerifiedProviderIdentity
from jobpilot_api.infrastructure.database.identity_repository import (
    SqlAlchemyIdentityUnitOfWork,
)
from jobpilot_api.infrastructure.database.models import IdentityRecord, UserRecord


def _identity(
    *,
    issuer: str = "https://tenant.example.invalid/",
    subject: str = "auth0|subject-1",
    email: str = "person@example.com",
) -> VerifiedProviderIdentity:
    return VerifiedProviderIdentity(
        issuer=issuer,
        subject=subject,
        verified_email=email,
        authorized_party="extension-client-id",
    )


def _service(engine: Engine) -> IdentityService:
    return IdentityService(lambda: SqlAlchemyIdentityUnitOfWork(engine))


def test_first_verified_identity_creates_minimal_user_and_mapping(
    migrated_engine: Engine,
) -> None:
    created = _service(migrated_engine).provision(_identity(email=" Person@Example.COM "))

    assert created.email == "person@example.com"
    assert created.display_name is None
    assert created.locale is None
    assert created.time_zone is None
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 1
        assert session.scalar(select(func.count()).select_from(IdentityRecord)) == 1


def test_repeat_identity_returns_same_user_without_duplicate_rows(
    migrated_engine: Engine,
) -> None:
    service = _service(migrated_engine)

    first = service.provision(_identity())
    second = service.provision(_identity())

    assert second.id == first.id
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 1
        assert session.scalar(select(func.count()).select_from(IdentityRecord)) == 1


def test_different_subjects_create_different_users(migrated_engine: Engine) -> None:
    service = _service(migrated_engine)

    first = service.provision(_identity(subject="auth0|subject-1", email="first@example.com"))
    second = service.provision(_identity(subject="auth0|subject-2", email="second@example.com"))

    assert second.id != first.id


def test_issuer_and_subject_remain_exact_case_sensitive_keys(migrated_engine: Engine) -> None:
    service = _service(migrated_engine)

    first = service.provision(_identity(subject="auth0|AbC", email="first@example.com"))
    second = service.provision(_identity(subject="auth0|abc", email="second@example.com"))
    third = service.provision(
        _identity(
            issuer="https://other.example.invalid/",
            subject="auth0|AbC",
            email="third@example.com",
        )
    )

    assert len({first.id, second.id, third.id}) == 3


def test_same_normalized_email_on_another_identity_is_a_conflict(
    migrated_engine: Engine,
) -> None:
    service = _service(migrated_engine)
    service.provision(_identity(subject="auth0|subject-1", email="Person@Example.COM"))

    with pytest.raises(IdentityConflictError):
        service.provision(_identity(subject="auth0|subject-2", email=" person@example.com "))

    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 1
        assert session.scalar(select(func.count()).select_from(IdentityRecord)) == 1


def test_existing_identity_synchronizes_changed_verified_email(
    migrated_engine: Engine,
) -> None:
    service = _service(migrated_engine)
    original = service.provision(_identity(email="old@example.com"))

    updated = service.provision(_identity(email="new@example.com"))

    assert updated.id == original.id
    assert updated.email == "new@example.com"


def test_email_synchronization_does_not_take_another_users_email(
    migrated_engine: Engine,
) -> None:
    service = _service(migrated_engine)
    service.provision(_identity(subject="auth0|subject-1", email="first@example.com"))
    service.provision(_identity(subject="auth0|subject-2", email="second@example.com"))

    with pytest.raises(IdentityConflictError):
        service.provision(_identity(subject="auth0|subject-1", email="second@example.com"))

    unchanged = service.resolve_existing("https://tenant.example.invalid/", "auth0|subject-1")
    assert unchanged.email == "first@example.com"


def test_unknown_identity_resolution_does_not_create_user(migrated_engine: Engine) -> None:
    service = _service(migrated_engine)

    with pytest.raises(AuthenticationRequiredError):
        service.resolve_existing("https://tenant.example.invalid/", "auth0|unknown")

    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 0


def test_deletion_pending_mapping_cannot_be_provisioned_or_resolved(
    migrated_engine: Engine,
) -> None:
    service = _service(migrated_engine)
    created = service.provision(_identity(email="old@example.com"))
    deletion_requested_at = datetime.now(UTC)
    with Session(migrated_engine) as session, session.begin():
        user = session.get(UserRecord, created.id)
        assert user is not None
        user.account_status = "deletion_pending"
        user.deletion_requested_at = deletion_requested_at

    with pytest.raises(AuthenticationRequiredError):
        service.provision(_identity(email="new@example.com"))
    with pytest.raises(AuthenticationRequiredError):
        service.resolve_existing("https://tenant.example.invalid/", "auth0|subject-1")

    with Session(migrated_engine) as session:
        stored_user = session.get(UserRecord, created.id)
        assert stored_user is not None
        assert stored_user.email == "old@example.com"
        assert stored_user.deletion_requested_at == deletion_requested_at
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 1
        assert session.scalar(select(func.count()).select_from(IdentityRecord)) == 1


class InitialMissSynchronizer:
    def __init__(self) -> None:
        self._barrier = Barrier(2)
        self._lock = Lock()
        self._remaining = 2

    def wait(self) -> None:
        with self._lock:
            should_wait = self._remaining > 0
            if should_wait:
                self._remaining -= 1
        if should_wait:
            self._barrier.wait(timeout=5)


class BarrierIdentityRepository:
    def __init__(
        self,
        delegate: IdentityRepository,
        synchronizer: InitialMissSynchronizer,
    ) -> None:
        self._delegate = delegate
        self._synchronizer = synchronizer

    def find_by_identity(self, issuer: str, subject: str) -> LocalUser | None:
        return self._delegate.find_by_identity(issuer, subject)

    def lock_by_identity(self, issuer: str, subject: str) -> LocalUser | None:
        user = self._delegate.lock_by_identity(issuer, subject)
        if user is None:
            self._synchronizer.wait()
        return user

    def find_by_email(self, normalized_email: str) -> LocalUser | None:
        return self._delegate.find_by_email(normalized_email)

    def create(
        self,
        identity: VerifiedProviderIdentity,
        normalized_email: str,
    ) -> LocalUser:
        return self._delegate.create(identity, normalized_email)

    def update_email(self, user_id: UUID, normalized_email: str) -> LocalUser:
        return self._delegate.update_email(user_id, normalized_email)


class BarrierUnitOfWork:
    def __init__(
        self,
        engine: Engine,
        synchronizer: InitialMissSynchronizer,
    ) -> None:
        self._delegate = SqlAlchemyIdentityUnitOfWork(engine)
        self._synchronizer = synchronizer

    def __enter__(self) -> BarrierUnitOfWork:
        self._delegate.__enter__()
        self.identities = BarrierIdentityRepository(
            self._delegate.identities,
            self._synchronizer,
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return self._delegate.__exit__(exc_type, exc_value, traceback)

    def commit(self) -> None:
        self._delegate.commit()


class EmailMissBarrierIdentityRepository(BarrierIdentityRepository):
    def __init__(
        self,
        delegate: IdentityRepository,
        synchronizer: InitialMissSynchronizer,
        target_email: str,
    ) -> None:
        super().__init__(delegate, synchronizer)
        self._target_email = target_email

    def lock_by_identity(self, issuer: str, subject: str) -> LocalUser | None:
        return self._delegate.lock_by_identity(issuer, subject)

    def find_by_email(self, normalized_email: str) -> LocalUser | None:
        user = self._delegate.find_by_email(normalized_email)
        if normalized_email == self._target_email and user is None:
            self._synchronizer.wait()
        return user


class EmailMissBarrierUnitOfWork(BarrierUnitOfWork):
    def __init__(
        self,
        engine: Engine,
        synchronizer: InitialMissSynchronizer,
        target_email: str,
    ) -> None:
        super().__init__(engine, synchronizer)
        self._target_email = target_email

    def __enter__(self) -> EmailMissBarrierUnitOfWork:
        self._delegate.__enter__()
        self.identities = EmailMissBarrierIdentityRepository(
            self._delegate.identities,
            self._synchronizer,
            self._target_email,
        )
        return self


def test_concurrent_provisioning_returns_one_user_and_no_orphan(
    migrated_engine: Engine,
) -> None:
    synchronizer = InitialMissSynchronizer()

    def provision() -> UUID:
        service = IdentityService(lambda: BarrierUnitOfWork(migrated_engine, synchronizer))
        return service.provision(_identity()).id

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(provision) for _ in range(2)]
        user_ids = [future.result() for future in futures]

    assert user_ids[0] == user_ids[1]
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 1
        assert session.scalar(select(func.count()).select_from(IdentityRecord)) == 1


def test_concurrent_same_identity_with_different_emails_reconciles_identity_constraint(
    migrated_engine: Engine,
) -> None:
    synchronizer = InitialMissSynchronizer()

    def provision(email: str) -> UUID:
        service = IdentityService(lambda: BarrierUnitOfWork(migrated_engine, synchronizer))
        return service.provision(_identity(email=email)).id

    emails = ["first@example.com", "second@example.com"]
    with ThreadPoolExecutor(max_workers=2) as executor:
        user_ids = list(executor.map(provision, emails))

    assert user_ids[0] == user_ids[1]
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 1
        assert session.scalar(select(func.count()).select_from(IdentityRecord)) == 1
        assert session.scalar(select(UserRecord.email)) in emails


def test_concurrent_different_identities_with_same_email_do_not_auto_link(
    migrated_engine: Engine,
) -> None:
    synchronizer = InitialMissSynchronizer()

    def provision(subject: str) -> str:
        service = IdentityService(lambda: BarrierUnitOfWork(migrated_engine, synchronizer))
        try:
            service.provision(_identity(subject=subject))
        except IdentityConflictError:
            return "conflict"
        return "created"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(provision, ["auth0|subject-1", "auth0|subject-2"]))

    assert sorted(outcomes) == ["conflict", "created"]
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 1
        assert session.scalar(select(func.count()).select_from(IdentityRecord)) == 1


def test_concurrent_email_updates_do_not_auto_link_different_identities(
    migrated_engine: Engine,
) -> None:
    service = _service(migrated_engine)
    service.provision(_identity(subject="auth0|subject-1", email="first@example.com"))
    service.provision(_identity(subject="auth0|subject-2", email="second@example.com"))
    synchronizer = InitialMissSynchronizer()
    target_email = "shared@example.com"

    def synchronize(subject: str) -> str:
        concurrent_service = IdentityService(
            lambda: EmailMissBarrierUnitOfWork(
                migrated_engine,
                synchronizer,
                target_email,
            )
        )
        try:
            concurrent_service.provision(_identity(subject=subject, email=target_email))
        except IdentityConflictError:
            return "conflict"
        return "updated"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(synchronize, ["auth0|subject-1", "auth0|subject-2"]))

    assert sorted(outcomes) == ["conflict", "updated"]
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 2
        assert session.scalar(select(func.count()).select_from(IdentityRecord)) == 2
        assert (
            session.scalar(
                select(func.count()).select_from(UserRecord).where(UserRecord.email == target_email)
            )
            == 1
        )
