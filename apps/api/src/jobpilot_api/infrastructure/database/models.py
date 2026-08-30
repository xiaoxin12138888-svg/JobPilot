from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Uuid as SqlUuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserRecord(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "account_status IN ('active', 'deletion_pending')",
            name="ck_users_account_status",
        ),
        CheckConstraint(
            "(account_status = 'active' AND deletion_requested_at IS NULL) OR "
            "(account_status = 'deletion_pending' AND deletion_requested_at IS NOT NULL)",
            name="ck_users_deletion_state",
        ),
        UniqueConstraint("email", name="uq_users_email"),
    )

    id: Mapped[UUID] = mapped_column(SqlUuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100))
    locale: Mapped[str | None] = mapped_column(String(35))
    time_zone: Mapped[str | None] = mapped_column(String(100))
    account_status: Mapped[str] = mapped_column(
        String(32),
        default="active",
        server_default="active",
    )
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class IdentityRecord(Base):
    __tablename__ = "identities"
    __table_args__ = (
        Index("ix_identities_user_id", "user_id"),
        UniqueConstraint("id", "user_id", name="uq_identities_id_user_id"),
        UniqueConstraint("issuer", "subject", name="uq_identities_issuer_subject"),
    )

    id: Mapped[UUID] = mapped_column(SqlUuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        SqlUuid,
        ForeignKey("users.id", name="fk_identities_user_id_users", ondelete="CASCADE"),
        nullable=False,
    )
    issuer: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class WebSessionRecord(Base):
    __tablename__ = "web_sessions"
    __table_args__ = (
        CheckConstraint(
            "octet_length(session_token_hash) = 32",
            name="ck_web_sessions_session_token_hash_length",
        ),
        CheckConstraint(
            "octet_length(csrf_token_hash) = 32",
            name="ck_web_sessions_csrf_token_hash_length",
        ),
        CheckConstraint(
            "created_at <= last_used_at "
            "AND last_used_at < idle_expires_at "
            "AND idle_expires_at <= absolute_expires_at",
            name="ck_web_sessions_expiry_order",
        ),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= last_used_at",
            name="ck_web_sessions_revocation_time",
        ),
        ForeignKeyConstraint(
            ["identity_id", "user_id"],
            ["identities.id", "identities.user_id"],
            name="fk_web_sessions_identity_user_identities",
            ondelete="CASCADE",
        ),
        Index("ix_web_sessions_user_id", "user_id"),
        Index("ix_web_sessions_identity_id", "identity_id"),
        Index("ix_web_sessions_absolute_expires_at", "absolute_expires_at"),
        UniqueConstraint(
            "session_token_hash",
            name="uq_web_sessions_session_token_hash",
        ),
    )

    id: Mapped[UUID] = mapped_column(SqlUuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        SqlUuid,
        ForeignKey("users.id", name="fk_web_sessions_user_id_users", ondelete="CASCADE"),
        nullable=False,
    )
    identity_id: Mapped[UUID] = mapped_column(SqlUuid, nullable=False)
    session_token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    csrf_token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginTransactionRecord(Base):
    __tablename__ = "login_transactions"
    __table_args__ = (
        CheckConstraint(
            "octet_length(browser_handle_hash) = 32",
            name="ck_login_transactions_browser_handle_hash_length",
        ),
        CheckConstraint(
            "octet_length(state_hash) = 32",
            name="ck_login_transactions_state_hash_length",
        ),
        CheckConstraint(
            "octet_length(nonce_hash) = 32",
            name="ck_login_transactions_nonce_hash_length",
        ),
        CheckConstraint(
            "char_length(pkce_verifier) BETWEEN 43 AND 128",
            name="ck_login_transactions_pkce_verifier_length",
        ),
        CheckConstraint(
            "intent IN ('login', 'signup')",
            name="ck_login_transactions_intent",
        ),
        CheckConstraint(
            "expires_at > created_at AND expires_at <= created_at + INTERVAL '600 seconds'",
            name="ck_login_transactions_expiry_order",
        ),
        Index("ix_login_transactions_expires_at", "expires_at"),
        UniqueConstraint(
            "browser_handle_hash",
            name="uq_login_transactions_browser_handle_hash",
        ),
        UniqueConstraint(
            "state_hash",
            name="uq_login_transactions_state_hash",
        ),
    )

    id: Mapped[UUID] = mapped_column(SqlUuid, primary_key=True, default=uuid4)
    browser_handle_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    state_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    pkce_verifier: Mapped[str] = mapped_column(String(128), nullable=False)
    intent: Mapped[str] = mapped_column(String(16), nullable=False)
    return_to: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
