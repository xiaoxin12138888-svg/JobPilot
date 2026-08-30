from __future__ import annotations

from types import TracebackType
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from jobpilot_api.application.identity_service import (
    IdentityPersistenceError,
    IdentityWriteConflict,
)
from jobpilot_api.domain.identity import AccountStatus, LocalUser, VerifiedProviderIdentity
from jobpilot_api.infrastructure.database.models import IdentityRecord, UserRecord

IDENTITY_UNIQUE_CONSTRAINTS = frozenset({"uq_users_email", "uq_identities_issuer_subject"})


class SqlAlchemyIdentityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_identity(self, issuer: str, subject: str) -> LocalUser | None:
        return self._find_by_identity(issuer, subject, lock=False)

    def lock_by_identity(self, issuer: str, subject: str) -> LocalUser | None:
        return self._find_by_identity(issuer, subject, lock=True)

    def find_by_email(self, normalized_email: str) -> LocalUser | None:
        record = self._session.scalar(
            select(UserRecord).where(UserRecord.email == normalized_email)
        )
        return _to_local_user(record) if record is not None else None

    def find_by_user_id(self, user_id: UUID) -> LocalUser | None:
        return self._find_by_user_id(user_id, lock=False)

    def lock_by_user_id(self, user_id: UUID) -> LocalUser | None:
        return self._find_by_user_id(user_id, lock=True)

    def create(
        self,
        identity: VerifiedProviderIdentity,
        normalized_email: str,
    ) -> LocalUser:
        user = UserRecord(email=normalized_email)
        self._session.add(user)
        self._session.flush()
        self._session.add(
            IdentityRecord(
                user_id=user.id,
                issuer=identity.issuer,
                subject=identity.subject,
            )
        )
        self._session.flush()
        self._session.refresh(user)
        return _to_local_user(user)

    def update_email(self, user_id: UUID, normalized_email: str) -> LocalUser:
        user = self._session.get(UserRecord, user_id)
        if user is None:
            raise IdentityPersistenceError
        user.email = normalized_email
        self._session.flush()
        self._session.refresh(user)
        return _to_local_user(user)

    def update_profile(
        self,
        user_id: UUID,
        *,
        display_name: str | None,
        locale: str | None,
        time_zone: str | None,
    ) -> LocalUser:
        user = self._session.get(UserRecord, user_id)
        if user is None:
            raise IdentityPersistenceError
        user.display_name = display_name
        user.locale = locale
        user.time_zone = time_zone
        self._session.flush()
        self._session.refresh(user)
        return _to_local_user(user)

    def _find_by_identity(
        self,
        issuer: str,
        subject: str,
        *,
        lock: bool,
    ) -> LocalUser | None:
        statement = (
            select(UserRecord)
            .join(IdentityRecord, IdentityRecord.user_id == UserRecord.id)
            .where(IdentityRecord.issuer == issuer, IdentityRecord.subject == subject)
        )
        if lock:
            statement = statement.with_for_update()
        record = self._session.scalar(statement)
        return _to_local_user(record) if record is not None else None

    def _find_by_user_id(self, user_id: UUID, *, lock: bool) -> LocalUser | None:
        statement = select(UserRecord).where(UserRecord.id == user_id)
        if lock:
            statement = statement.with_for_update()
        record = self._session.scalar(statement)
        return _to_local_user(record) if record is not None else None


class SqlAlchemyIdentityUnitOfWork:
    def __init__(self, engine: Engine) -> None:
        self._session = Session(engine, expire_on_commit=False)
        self.identities = SqlAlchemyIdentityRepository(self._session)

    def __enter__(self) -> SqlAlchemyIdentityUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        cleanup_failed = False
        try:
            if exc_value is not None:
                try:
                    self._session.rollback()
                except SQLAlchemyError:
                    cleanup_failed = True
        finally:
            try:
                self._session.close()
            except SQLAlchemyError:
                cleanup_failed = True

        if cleanup_failed:
            raise IdentityPersistenceError from None

        if isinstance(exc_value, IntegrityError):
            constraint_name = getattr(
                getattr(exc_value.orig, "diag", None), "constraint_name", None
            )
            if constraint_name in IDENTITY_UNIQUE_CONSTRAINTS:
                raise IdentityWriteConflict from None
            raise IdentityPersistenceError from None
        if isinstance(exc_value, SQLAlchemyError):
            raise IdentityPersistenceError from None

    def commit(self) -> None:
        self._session.commit()


def _to_local_user(record: UserRecord) -> LocalUser:
    return LocalUser(
        id=record.id,
        email=record.email,
        display_name=record.display_name,
        locale=record.locale,
        time_zone=record.time_zone,
        account_status=AccountStatus(record.account_status),
        deletion_requested_at=record.deletion_requested_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
