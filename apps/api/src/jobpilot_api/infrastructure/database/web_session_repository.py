from __future__ import annotations

from datetime import datetime
from types import TracebackType
from uuid import UUID

from sqlalchemy import Engine, and_, delete, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from jobpilot_api.application.web_session_service import (
    WebSessionIdentityNotFoundError,
    WebSessionPersistenceError,
)
from jobpilot_api.domain.web_session import LoginTransaction, WebSession
from jobpilot_api.infrastructure.database.models import (
    IdentityRecord,
    LoginTransactionRecord,
    UserRecord,
    WebSessionRecord,
)

LOGIN_TRANSACTION_PRUNE_BATCH = 100


class SqlAlchemyWebSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

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
    ) -> WebSession:
        identity_id = self._session.scalar(
            select(IdentityRecord.id)
            .join(UserRecord, UserRecord.id == IdentityRecord.user_id)
            .where(
                IdentityRecord.user_id == user_id,
                IdentityRecord.issuer == identity_issuer,
                IdentityRecord.subject == identity_subject,
                UserRecord.account_status == "active",
            )
        )
        if identity_id is None:
            raise WebSessionIdentityNotFoundError

        record = WebSessionRecord(
            user_id=user_id,
            identity_id=identity_id,
            session_token_hash=session_token_hash,
            csrf_token_hash=csrf_token_hash,
            created_at=created_at,
            last_used_at=last_used_at,
            idle_expires_at=idle_expires_at,
            absolute_expires_at=absolute_expires_at,
        )
        self._session.add(record)
        self._session.flush()
        return _to_web_session(record, identity_issuer, identity_subject)

    def find_active_by_token_hash(
        self,
        session_token_hash: bytes,
        *,
        now: datetime,
    ) -> WebSession | None:
        row = self._session.execute(
            select(
                WebSessionRecord,
                IdentityRecord.issuer,
                IdentityRecord.subject,
            )
            .join(
                IdentityRecord,
                and_(
                    IdentityRecord.id == WebSessionRecord.identity_id,
                    IdentityRecord.user_id == WebSessionRecord.user_id,
                ),
            )
            .join(UserRecord, UserRecord.id == WebSessionRecord.user_id)
            .where(
                WebSessionRecord.session_token_hash == session_token_hash,
                WebSessionRecord.revoked_at.is_(None),
                WebSessionRecord.idle_expires_at > now,
                WebSessionRecord.absolute_expires_at > now,
                UserRecord.account_status == "active",
            )
        ).one_or_none()
        if row is None:
            return None
        record, identity_issuer, identity_subject = row
        return _to_web_session(record, identity_issuer, identity_subject)

    def revoke(self, session_id: UUID, *, revoked_at: datetime) -> None:
        record = self._session.scalar(
            select(WebSessionRecord).where(WebSessionRecord.id == session_id).with_for_update()
        )
        if record is not None and record.revoked_at is None:
            record.revoked_at = revoked_at
            self._session.flush()


class SqlAlchemyLoginTransactionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def delete_expired(self, *, now: datetime) -> None:
        expired_ids = tuple(
            self._session.scalars(
                select(LoginTransactionRecord.id)
                .where(LoginTransactionRecord.expires_at <= now)
                .order_by(LoginTransactionRecord.expires_at, LoginTransactionRecord.id)
                .limit(LOGIN_TRANSACTION_PRUNE_BATCH)
                .with_for_update(skip_locked=True)
            )
        )
        if expired_ids:
            self._session.execute(
                delete(LoginTransactionRecord).where(LoginTransactionRecord.id.in_(expired_ids))
            )

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
        record = LoginTransactionRecord(
            browser_handle_hash=browser_handle_hash,
            state_hash=state_hash,
            nonce_hash=nonce_hash,
            pkce_verifier=pkce_verifier,
            intent=intent,
            return_to=return_to,
            created_at=created_at,
            expires_at=expires_at,
        )
        self._session.add(record)
        self._session.flush()
        return _to_login_transaction(record)

    def consume(
        self,
        *,
        browser_handle_hash: bytes | None,
        state_hash: bytes | None,
        now: datetime,
    ) -> LoginTransaction | None:
        identifying_predicates = []
        if browser_handle_hash is not None:
            identifying_predicates.append(
                LoginTransactionRecord.browser_handle_hash == browser_handle_hash
            )
        if state_hash is not None:
            identifying_predicates.append(LoginTransactionRecord.state_hash == state_hash)
        if not identifying_predicates:
            return None

        records = list(
            self._session.scalars(
                select(LoginTransactionRecord)
                .where(or_(*identifying_predicates))
                .order_by(LoginTransactionRecord.id)
                .with_for_update()
            )
        )
        matched = None
        if browser_handle_hash is not None and state_hash is not None:
            matched = next(
                (
                    record
                    for record in records
                    if record.browser_handle_hash == browser_handle_hash
                    and record.state_hash == state_hash
                ),
                None,
            )

        result = (
            _to_login_transaction(matched)
            if matched is not None and now < matched.expires_at
            else None
        )
        for record in records:
            self._session.delete(record)
        self._session.flush()
        return result


class SqlAlchemyWebSessionUnitOfWork:
    def __init__(self, engine: Engine) -> None:
        self._session = Session(engine, expire_on_commit=False)
        self.sessions = SqlAlchemyWebSessionRepository(self._session)
        self.login_transactions = SqlAlchemyLoginTransactionRepository(self._session)

    def __enter__(self) -> SqlAlchemyWebSessionUnitOfWork:
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
            raise WebSessionPersistenceError from None
        if isinstance(exc_value, SQLAlchemyError):
            raise WebSessionPersistenceError from None

    def commit(self) -> None:
        self._session.commit()


def _to_web_session(
    record: WebSessionRecord,
    identity_issuer: str,
    identity_subject: str,
) -> WebSession:
    return WebSession(
        id=record.id,
        user_id=record.user_id,
        identity_issuer=identity_issuer,
        identity_subject=identity_subject,
        csrf_token_hash=record.csrf_token_hash,
        created_at=record.created_at,
        last_used_at=record.last_used_at,
        idle_expires_at=record.idle_expires_at,
        absolute_expires_at=record.absolute_expires_at,
        revoked_at=record.revoked_at,
    )


def _to_login_transaction(record: LoginTransactionRecord) -> LoginTransaction:
    return LoginTransaction(
        id=record.id,
        browser_handle_hash=record.browser_handle_hash,
        state_hash=record.state_hash,
        nonce_hash=record.nonce_hash,
        pkce_verifier=record.pkce_verifier,
        intent=record.intent,
        return_to=record.return_to,
        created_at=record.created_at,
        expires_at=record.expires_at,
    )
