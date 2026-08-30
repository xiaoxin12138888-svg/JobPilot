from __future__ import annotations

from dataclasses import replace
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
    InvalidProfileUpdateError,
    InvalidVerifiedIdentityError,
)
from jobpilot_api.domain.identity import (
    AccountStatus,
    AuthenticatedUser,
    LocalUser,
    SessionKind,
    VerifiedProviderIdentity,
)


def _user(
    status: AccountStatus = AccountStatus.ACTIVE,
    *,
    display_name: str | None = None,
    locale: str | None = None,
    time_zone: str | None = None,
) -> LocalUser:
    now = datetime.now(UTC)
    return LocalUser(
        id=uuid4(),
        email="person@example.com",
        display_name=display_name,
        locale=locale,
        time_zone=time_zone,
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
        user_by_id: LocalUser | None = None,
    ) -> None:
        self.identity_user = identity_user
        self.email_user = email_user
        self.created_user = created_user or _user()
        self.user_by_id = user_by_id
        self.create_call: tuple[VerifiedProviderIdentity, str] | None = None
        self.profile_update_call: tuple[UUID, str | None, str | None, str | None] | None = None
        self.find_by_user_id_count = 0
        self.lock_by_user_id_count = 0

    def find_by_identity(self, issuer: str, subject: str) -> LocalUser | None:
        return self.identity_user

    def lock_by_identity(self, issuer: str, subject: str) -> LocalUser | None:
        return self.identity_user

    def find_by_email(self, normalized_email: str) -> LocalUser | None:
        return self.email_user

    def find_by_user_id(self, user_id: UUID) -> LocalUser | None:
        self.find_by_user_id_count += 1
        return self.user_by_id

    def lock_by_user_id(self, user_id: UUID) -> LocalUser | None:
        self.lock_by_user_id_count += 1
        return self.user_by_id

    def create(
        self,
        identity: VerifiedProviderIdentity,
        normalized_email: str,
    ) -> LocalUser:
        self.create_call = (identity, normalized_email)
        return self.created_user

    def update_email(self, user_id: UUID, normalized_email: str) -> LocalUser:
        raise AssertionError("email update was not expected")

    def update_profile(
        self,
        user_id: UUID,
        *,
        display_name: str | None,
        locale: str | None,
        time_zone: str | None,
    ) -> LocalUser:
        if self.user_by_id is None:
            raise AssertionError("profile update requires an existing user")
        self.profile_update_call = (user_id, display_name, locale, time_zone)
        return replace(
            self.user_by_id,
            display_name=display_name,
            locale=locale,
            time_zone=time_zone,
        )


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


def _authenticated_user(user: LocalUser) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user.id,
        identity_issuer="https://tenant.example.invalid/",
        identity_subject="auth0|subject-1",
        session_kind=SessionKind.EXTENSION,
        session_id=None,
    )


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

    with pytest.raises(InvalidVerifiedIdentityError, match="254"):
        service.provision(identity)

    assert repository.create_call is None


def test_provision_rechecks_length_after_unicode_email_normalization() -> None:
    unit_of_work_opened = False

    def open_unit_of_work() -> RecordingUnitOfWork:
        nonlocal unit_of_work_opened
        unit_of_work_opened = True
        return RecordingUnitOfWork(RecordingIdentityRepository())

    identity = _identity(f"{'İ' * 127}@x")
    assert len(identity.verified_email) < 254

    with pytest.raises(InvalidVerifiedIdentityError, match="254"):
        IdentityService(open_unit_of_work).provision(identity)

    assert unit_of_work_opened is False


def test_resolve_existing_never_provisions_an_unknown_identity() -> None:
    repository = RecordingIdentityRepository()
    service = IdentityService(lambda: RecordingUnitOfWork(repository))

    with pytest.raises(AuthenticationRequiredError):
        service.resolve_existing("https://tenant.example.invalid/", "auth0|unknown")

    assert repository.create_call is None


def test_authenticate_existing_builds_the_provider_neutral_principal() -> None:
    existing_user = _user()
    repository = RecordingIdentityRepository(identity_user=existing_user)
    service = IdentityService(lambda: RecordingUnitOfWork(repository))

    authenticated_user = service.authenticate_existing(
        _identity(),
        session_kind=SessionKind.EXTENSION,
    )

    assert authenticated_user == AuthenticatedUser(
        user_id=existing_user.id,
        identity_issuer="https://tenant.example.invalid/",
        identity_subject="auth0|subject-1",
        session_kind=SessionKind.EXTENSION,
        session_id=None,
    )
    assert repository.create_call is None


def test_get_active_user_requires_an_existing_active_local_user() -> None:
    existing_user = _user(display_name="Lin")
    repository = RecordingIdentityRepository(user_by_id=existing_user)
    service = IdentityService(lambda: RecordingUnitOfWork(repository))

    assert service.get_active_user(_authenticated_user(existing_user)) == existing_user
    assert repository.find_by_user_id_count == 1
    assert repository.lock_by_user_id_count == 0


def test_update_profile_merges_only_explicit_fields_under_an_active_user_lock() -> None:
    existing_user = _user(
        display_name="Old name",
        locale="zh-CN",
        time_zone="Asia/Shanghai",
    )
    repository = RecordingIdentityRepository(user_by_id=existing_user)
    unit_of_work = RecordingUnitOfWork(repository)
    service = IdentityService(lambda: unit_of_work)

    updated = service.update_profile(_authenticated_user(existing_user), display_name=None)

    assert updated.display_name is None
    assert updated.locale == "zh-CN"
    assert updated.time_zone == "Asia/Shanghai"
    assert repository.profile_update_call == (
        existing_user.id,
        None,
        "zh-CN",
        "Asia/Shanghai",
    )
    assert repository.find_by_user_id_count == 0
    assert repository.lock_by_user_id_count == 1
    assert unit_of_work.commit_count == 1


def test_update_profile_rejects_an_empty_patch_before_opening_a_unit_of_work() -> None:
    unit_of_work_opened = False

    def open_unit_of_work() -> RecordingUnitOfWork:
        nonlocal unit_of_work_opened
        unit_of_work_opened = True
        return RecordingUnitOfWork(RecordingIdentityRepository())

    with pytest.raises(InvalidProfileUpdateError, match="at least one"):
        IdentityService(open_unit_of_work).update_profile(_authenticated_user(_user()))

    assert unit_of_work_opened is False


@pytest.mark.parametrize("operation", ["get", "update"])
def test_profile_operations_reject_a_deletion_pending_user(operation: str) -> None:
    user = _user(AccountStatus.DELETION_PENDING)
    repository = RecordingIdentityRepository(user_by_id=user)
    unit_of_work = RecordingUnitOfWork(repository)
    service = IdentityService(lambda: unit_of_work)

    with pytest.raises(AuthenticationRequiredError):
        if operation == "get":
            service.get_active_user(_authenticated_user(user))
        else:
            service.update_profile(_authenticated_user(user), locale="zh-CN")

    assert repository.profile_update_call is None
    assert unit_of_work.commit_count == 0


@pytest.mark.parametrize("operation", ["get", "update"])
def test_profile_persistence_errors_are_sanitized(operation: str) -> None:
    user = _user()

    class FailingRepository(RecordingIdentityRepository):
        def find_by_user_id(self, user_id: UUID) -> LocalUser | None:
            raise IdentityPersistenceError("database-private-detail")

        def lock_by_user_id(self, user_id: UUID) -> LocalUser | None:
            raise IdentityPersistenceError("database-private-detail")

    service = IdentityService(lambda: RecordingUnitOfWork(FailingRepository(user_by_id=user)))

    with pytest.raises(IdentityStoreUnavailableError) as captured:
        if operation == "get":
            service.get_active_user(_authenticated_user(user))
        else:
            service.update_profile(_authenticated_user(user), locale="zh-CN")

    assert str(captured.value) == ""


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
