from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Protocol
from uuid import UUID

from jobpilot_api.domain.identity import AccountStatus, LocalUser, VerifiedProviderIdentity


class AuthenticationRequiredError(Exception):
    """The identity cannot enter the authenticated application boundary."""


class IdentityConflictError(Exception):
    """A verified email belongs to a different local identity."""


class IdentityStoreUnavailableError(Exception):
    """The identity store could not establish a trustworthy outcome."""


class IdentityWriteConflict(Exception):
    """An approved identity uniqueness constraint won a concurrent write."""


class IdentityPersistenceError(Exception):
    """An unexpected persistence failure occurred without sensitive detail."""


class IdentityRepository(Protocol):
    def find_by_identity(self, issuer: str, subject: str) -> LocalUser | None: ...

    def lock_by_identity(self, issuer: str, subject: str) -> LocalUser | None: ...

    def find_by_email(self, normalized_email: str) -> LocalUser | None: ...

    def create(
        self,
        identity: VerifiedProviderIdentity,
        normalized_email: str,
    ) -> LocalUser: ...

    def update_email(self, user_id: UUID, normalized_email: str) -> LocalUser: ...


class IdentityUnitOfWork(Protocol):
    identities: IdentityRepository

    def __enter__(self) -> IdentityUnitOfWork: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


class IdentityService:
    def __init__(self, unit_of_work_factory: Callable[[], IdentityUnitOfWork]) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def provision(self, identity: VerifiedProviderIdentity) -> LocalUser:
        normalized_email = _normalize_verified_email(identity.verified_email)
        try:
            return self._provision_once(identity, normalized_email)
        except IdentityWriteConflict:
            try:
                return self._reconcile_write_conflict(identity, normalized_email)
            except (IdentityPersistenceError, IdentityWriteConflict) as error:
                raise IdentityStoreUnavailableError from error
        except IdentityPersistenceError as error:
            raise IdentityStoreUnavailableError from error

    def resolve_existing(self, issuer: str, subject: str) -> LocalUser:
        try:
            with self._unit_of_work_factory() as unit_of_work:
                user = unit_of_work.identities.find_by_identity(issuer, subject)
                if user is None:
                    raise AuthenticationRequiredError
                return _require_active(user)
        except IdentityPersistenceError as error:
            raise IdentityStoreUnavailableError from error

    def _provision_once(
        self,
        identity: VerifiedProviderIdentity,
        normalized_email: str,
    ) -> LocalUser:
        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.identities.lock_by_identity(identity.issuer, identity.subject)
            if user is None:
                user = unit_of_work.identities.create(identity, normalized_email)
            else:
                user = _synchronize_email(unit_of_work.identities, user, normalized_email)
            unit_of_work.commit()
            return user

    def _reconcile_write_conflict(
        self,
        identity: VerifiedProviderIdentity,
        normalized_email: str,
    ) -> LocalUser:
        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.identities.lock_by_identity(identity.issuer, identity.subject)
            if user is None:
                if unit_of_work.identities.find_by_email(normalized_email) is not None:
                    raise IdentityConflictError
                raise IdentityStoreUnavailableError
            user = _synchronize_email(unit_of_work.identities, user, normalized_email)
            unit_of_work.commit()
            return user


def _synchronize_email(
    repository: IdentityRepository,
    user: LocalUser,
    normalized_email: str,
) -> LocalUser:
    _require_active(user)
    if user.email == normalized_email:
        return user
    email_owner = repository.find_by_email(normalized_email)
    if email_owner is not None and email_owner.id != user.id:
        raise IdentityConflictError
    return repository.update_email(user.id, normalized_email)


def _normalize_verified_email(email: str) -> str:
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise ValueError("verified email must not be empty")
    if len(normalized_email) > 254:
        raise ValueError("verified email must not exceed 254 characters")
    return normalized_email


def _require_active(user: LocalUser) -> LocalUser:
    if user.account_status is not AccountStatus.ACTIVE:
        raise AuthenticationRequiredError
    return user
