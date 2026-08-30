from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from jobpilot_api.application.identity_service import (
    AuthenticationRequiredError,
    IdentityPersistenceError,
    IdentityService,
    IdentityStoreUnavailableError,
    IdentityWriteConflict,
)
from jobpilot_api.domain.identity import AccountStatus, LocalUser, VerifiedProviderIdentity


def _user(status: AccountStatus = AccountStatus.ACTIVE) -> LocalUser:
    now = datetime.now(UTC)
    return LocalUser(
        id=uuid4(),
        email="person@example.com",
        display_name=None,
        locale=None,
        time_zone=None,
        account_status=status,
        deletion_requested_at=now if status is AccountStatus.DELETION_PENDING else None,
        created_at=now,
        updated_at=now,
    )


def _identity(email: str = "person@example.com") -> VerifiedProviderIdentity:
    return VerifiedProviderIdentity(
        issuer="https://tenant.example.invalid/",
        subject="auth0|subject-1",
        verified_email=email,
        authorized_party="extension-client-id",
    )


class RecordingIdentityRepository:
    def __init__(
        self,
        *,
        identity_user: LocalUser | None = None,
        email_user: LocalUser | None = None,
        created_user: LocalUser | None = None,
    ) -> None:
        self.identity_user = identity_user
        self.email_user = email_user
        self.created_user = created_user or _user()
        self.create_call: tuple[VerifiedProviderIdentity, str] | None = None

    def find_by_identity(self, issuer: str, subject: str) -> LocalUser | None:
        return self.identity_user

    def lock_by_identity(self, issuer: str, subject: str) -> LocalUser | None:
        return self.identity_user

    def find_by_email(self, normalized_email: str) -> LocalUser | None:
        return self.email_user

    def create(
        self,
        identity: VerifiedProviderIdentity,
        normalized_email: str,
    ) -> LocalUser:
        self.create_call = (identity, normalized_email)
        return self.created_user

    def update_email(self, user_id: UUID, normalized_email: str) -> LocalUser:
        raise AssertionError("email update was not expected")


class RecordingUnitOfWork:
    def __init__(self, repository: RecordingIdentityRepository) -> None:
        self.identities = repository
        self.commit_count = 0

    def __enter__(self) -> RecordingUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def commit(self) -> None:
        self.commit_count += 1


def test_provision_normalizes_verified_email_before_persistence() -> None:
    repository = RecordingIdentityRepository(created_user=_user())
    unit_of_work = RecordingUnitOfWork(repository)
    service = IdentityService(lambda: unit_of_work)
    identity = _identity("  Person@Example.COM  ")

    result = service.provision(identity)

    assert result.id == repository.created_user.id
    assert repository.create_call == (identity, "person@example.com")
    assert unit_of_work.commit_count == 1


def test_provision_rejects_email_longer_than_contract_limit() -> None:
    repository = RecordingIdentityRepository(created_user=_user())
    service = IdentityService(lambda: RecordingUnitOfWork(repository))
    identity = _identity(f"{'a' * 245}@example.com")

    with pytest.raises(ValueError, match="254"):
        service.provision(identity)

    assert repository.create_call is None


def test_resolve_existing_never_provisions_an_unknown_identity() -> None:
    repository = RecordingIdentityRepository()
    service = IdentityService(lambda: RecordingUnitOfWork(repository))

    with pytest.raises(AuthenticationRequiredError):
        service.resolve_existing("https://tenant.example.invalid/", "auth0|unknown")

    assert repository.create_call is None


@pytest.mark.parametrize("operation", ["provision", "resolve"])
def test_deletion_pending_identity_cannot_be_reactivated(operation: str) -> None:
    repository = RecordingIdentityRepository(identity_user=_user(AccountStatus.DELETION_PENDING))
    unit_of_work = RecordingUnitOfWork(repository)
    service = IdentityService(lambda: unit_of_work)

    with pytest.raises(AuthenticationRequiredError):
        if operation == "provision":
            service.provision(_identity())
        else:
            service.resolve_existing("https://tenant.example.invalid/", "auth0|subject-1")

    assert unit_of_work.commit_count == 0


def test_known_write_conflict_reconciles_to_concurrent_identity_winner() -> None:
    winner = _user()

    class ConflictingRepository(RecordingIdentityRepository):
        def create(
            self,
            identity: VerifiedProviderIdentity,
            normalized_email: str,
        ) -> LocalUser:
            raise IdentityWriteConflict

    units_of_work = iter(
        [
            RecordingUnitOfWork(ConflictingRepository()),
            RecordingUnitOfWork(RecordingIdentityRepository(identity_user=winner)),
        ]
    )
    service = IdentityService(lambda: next(units_of_work))

    assert service.provision(_identity()).id == winner.id


def test_identity_winner_visible_by_email_does_not_become_a_false_conflict() -> None:
    winner = _user()

    class ConflictingRepository(RecordingIdentityRepository):
        def create(
            self,
            identity: VerifiedProviderIdentity,
            normalized_email: str,
        ) -> LocalUser:
            raise IdentityWriteConflict

    units_of_work = iter(
        [
            RecordingUnitOfWork(ConflictingRepository(email_user=winner)),
            RecordingUnitOfWork(RecordingIdentityRepository(identity_user=winner)),
        ]
    )
    service = IdentityService(lambda: next(units_of_work))

    assert service.provision(_identity()).id == winner.id


def test_ambiguous_state_after_write_conflict_fails_closed() -> None:
    class ConflictingRepository(RecordingIdentityRepository):
        def create(
            self,
            identity: VerifiedProviderIdentity,
            normalized_email: str,
        ) -> LocalUser:
            raise IdentityWriteConflict

    units_of_work = iter(
        [
            RecordingUnitOfWork(ConflictingRepository()),
            RecordingUnitOfWork(RecordingIdentityRepository()),
        ]
    )
    service = IdentityService(lambda: next(units_of_work))

    with pytest.raises(IdentityStoreUnavailableError):
        service.provision(_identity())


def test_unexpected_persistence_error_is_not_reported_as_identity_conflict() -> None:
    class FailingRepository(RecordingIdentityRepository):
        def find_by_identity(self, issuer: str, subject: str) -> LocalUser | None:
            raise IdentityPersistenceError

    service = IdentityService(lambda: RecordingUnitOfWork(FailingRepository(identity_user=_user())))

    with pytest.raises(IdentityStoreUnavailableError):
        service.resolve_existing("https://tenant.example.invalid/", "auth0|subject-1")
