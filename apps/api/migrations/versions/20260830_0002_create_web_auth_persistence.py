"""Create Web sessions and login transactions.

Revision ID: 20260830_0002
Revises: 20260830_0001
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0002"
down_revision: str | None = "20260830_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_identities_id_user_id",
        "identities",
        ["id", "user_id"],
    )
    op.create_table(
        "web_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("identity_id", sa.Uuid(), nullable=False),
        sa.Column("session_token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("csrf_token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "octet_length(session_token_hash) = 32",
            name="ck_web_sessions_session_token_hash_length",
        ),
        sa.CheckConstraint(
            "octet_length(csrf_token_hash) = 32",
            name="ck_web_sessions_csrf_token_hash_length",
        ),
        sa.CheckConstraint(
            "created_at <= last_used_at "
            "AND last_used_at < idle_expires_at "
            "AND idle_expires_at <= absolute_expires_at",
            name="ck_web_sessions_expiry_order",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= last_used_at",
            name="ck_web_sessions_revocation_time",
        ),
        sa.ForeignKeyConstraint(
            ["identity_id", "user_id"],
            ["identities.id", "identities.user_id"],
            name="fk_web_sessions_identity_user_identities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_web_sessions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_web_sessions"),
        sa.UniqueConstraint(
            "session_token_hash",
            name="uq_web_sessions_session_token_hash",
        ),
    )
    op.create_index(
        "ix_web_sessions_user_id",
        "web_sessions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_web_sessions_identity_id",
        "web_sessions",
        ["identity_id"],
        unique=False,
    )
    op.create_index(
        "ix_web_sessions_absolute_expires_at",
        "web_sessions",
        ["absolute_expires_at"],
        unique=False,
    )

    op.create_table(
        "login_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("browser_handle_hash", sa.LargeBinary(), nullable=False),
        sa.Column("state_hash", sa.LargeBinary(), nullable=False),
        sa.Column("nonce_hash", sa.LargeBinary(), nullable=False),
        sa.Column("pkce_verifier", sa.String(length=128), nullable=False),
        sa.Column("intent", sa.String(length=16), nullable=False),
        sa.Column("return_to", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "octet_length(browser_handle_hash) = 32",
            name="ck_login_transactions_browser_handle_hash_length",
        ),
        sa.CheckConstraint(
            "octet_length(state_hash) = 32",
            name="ck_login_transactions_state_hash_length",
        ),
        sa.CheckConstraint(
            "octet_length(nonce_hash) = 32",
            name="ck_login_transactions_nonce_hash_length",
        ),
        sa.CheckConstraint(
            "char_length(pkce_verifier) BETWEEN 43 AND 128",
            name="ck_login_transactions_pkce_verifier_length",
        ),
        sa.CheckConstraint(
            "intent IN ('login', 'signup')",
            name="ck_login_transactions_intent",
        ),
        sa.CheckConstraint(
            "expires_at > created_at AND expires_at <= created_at + INTERVAL '600 seconds'",
            name="ck_login_transactions_expiry_order",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_login_transactions"),
        sa.UniqueConstraint(
            "browser_handle_hash",
            name="uq_login_transactions_browser_handle_hash",
        ),
        sa.UniqueConstraint(
            "state_hash",
            name="uq_login_transactions_state_hash",
        ),
    )
    op.create_index(
        "ix_login_transactions_expires_at",
        "login_transactions",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_login_transactions_expires_at",
        table_name="login_transactions",
    )
    op.drop_table("login_transactions")
    op.drop_index(
        "ix_web_sessions_absolute_expires_at",
        table_name="web_sessions",
    )
    op.drop_index("ix_web_sessions_identity_id", table_name="web_sessions")
    op.drop_index("ix_web_sessions_user_id", table_name="web_sessions")
    op.drop_table("web_sessions")
    op.drop_constraint(
        "uq_identities_id_user_id",
        "identities",
        type_="unique",
    )
