from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
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
