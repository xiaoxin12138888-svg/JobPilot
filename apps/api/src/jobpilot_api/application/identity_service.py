from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Protocol
from uuid import UUID

from jobpilot_api.domain.identity import (
    AccountStatus,
    AuthenticatedUser,
    LocalUser,
    SessionKind,
    VerifiedProviderIdentity,
)


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


class InvalidVerifiedIdentityError(ValueError):
    """A verified provider attribute cannot satisfy the local identity contract."""


class InvalidProfileUpdateError(ValueError):
    """A profile update does not contain an allowed change."""


class _NotProvided:
    pass


_NOT_PROVIDED = _NotProvided()


class IdentityRepository(Protocol):
    def find_by_identity(self, issuer: str, subject: str) -> LocalUser | None: ...

    def lock_by_identity(self, issuer: str, subject: str) -> LocalUser | None: ...

    def find_by_email(self, normalized_email: str) -> LocalUser | None: ...

    def find_by_user_id(self, user_id: UUID) -> LocalUser | None: ...

    def lock_by_user_id(self, user_id: UUID) -> LocalUser | None: ...

    def create(
        self,
        identity: VerifiedProviderIdentity,
        normalized_email: str,
    ) -> LocalUser: ...

    def update_email(self, user_id: UUID, normalized_email: str) -> LocalUser: ...

    def update_profile(
        self,
        user_id: UUID,
        *,
        display_name: str | None,
        locale: str | None,
        time_zone: str | None,
    ) -> LocalUser: ...


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

    def authenticate_existing(
        self,
        identity: VerifiedProviderIdentity,
        *,
        session_kind: SessionKind,
        session_id: UUID | None = None,
    ) -> AuthenticatedUser:
        user = self.resolve_existing(identity.issuer, identity.subject)
        return AuthenticatedUser(
            user_id=user.id,
            identity_issuer=identity.issuer,
            identity_subject=identity.subject,
            session_kind=session_kind,
            session_id=session_id,
        )

    def get_active_user(self, authenticated_user: AuthenticatedUser) -> LocalUser:
        try:
            with self._unit_of_work_factory() as unit_of_work:
                user = unit_of_work.identities.find_by_user_id(authenticated_user.user_id)
                if user is None:
                    raise AuthenticationRequiredError
                return _require_active(user)
        except IdentityPersistenceError as error:
            raise IdentityStoreUnavailableError from error

    def update_profile(
        self,
        authenticated_user: AuthenticatedUser,
        *,
        display_name: str | None | _NotProvided = _NOT_PROVIDED,
        locale: str | None | _NotProvided = _NOT_PROVIDED,
        time_zone: str | None | _NotProvided = _NOT_PROVIDED,
    ) -> LocalUser:
        if all(value is _NOT_PROVIDED for value in (display_name, locale, time_zone)):
            raise InvalidProfileUpdateError("at least one profile field must be provided")
        try:
            with self._unit_of_work_factory() as unit_of_work:
                user = unit_of_work.identities.lock_by_user_id(authenticated_user.user_id)
                if user is None:
                    raise AuthenticationRequiredError
                user = _require_active(user)
                updated = unit_of_work.identities.update_profile(
                    authenticated_user.user_id,
                    display_name=_merge_profile_value(user.display_name, display_name),
                    locale=_merge_profile_value(user.locale, locale),
                    time_zone=_merge_profile_value(user.time_zone, time_zone),
                )
                unit_of_work.commit()
                return updated
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
        raise InvalidVerifiedIdentityError("verified email must not be empty")
    if len(normalized_email) > 254:
        raise InvalidVerifiedIdentityError("verified email must not exceed 254 characters")
    return normalized_email


def _merge_profile_value(
    current: str | None,
    update: str | None | _NotProvided,
) -> str | None:
    if update is _NOT_PROVIDED:
        return current
    return update


def _require_active(user: LocalUser) -> LocalUser:
    if user.account_status is not AccountStatus.ACTIVE:
        raise AuthenticationRequiredError
    return user
