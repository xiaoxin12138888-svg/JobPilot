from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import LargeBinary, String, Text, Uuid, inspect, text

from jobpilot_api.infrastructure.database.engine import create_database_engine


def test_database_engine_rejects_non_postgresql_urls() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        create_database_engine("sqlite+pysqlite:///:memory:")


def test_migration_history_has_one_head(alembic_config: Config) -> None:
    script = ScriptDirectory.from_config(alembic_config)

    assert len(script.get_heads()) == 1


def test_auth_persistence_migrations_upgrade_downgrade_and_upgrade(
    alembic_config: Config,
    database_url: str,
) -> None:
    engine = create_database_engine(database_url)
    try:
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "20260830_0001")

        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        assert {"users", "identities"}.issubset(table_names)
        assert "web_sessions" not in table_names
        assert "login_transactions" not in table_names

        user_columns = {column["name"]: column for column in inspector.get_columns("users")}
        assert set(user_columns) == {
            "id",
            "email",
            "display_name",
            "locale",
            "time_zone",
            "account_status",
            "deletion_requested_at",
            "created_at",
            "updated_at",
        }
        assert isinstance(user_columns["id"]["type"], Uuid)
        assert user_columns["id"]["nullable"] is False
        assert isinstance(user_columns["email"]["type"], String)
        assert user_columns["email"]["type"].length == 254
        assert user_columns["email"]["nullable"] is False
        assert user_columns["display_name"]["type"].length == 100
        assert user_columns["display_name"]["nullable"] is True
        assert user_columns["locale"]["type"].length == 35
        assert user_columns["locale"]["nullable"] is True
        assert user_columns["time_zone"]["type"].length == 100
        assert user_columns["time_zone"]["nullable"] is True
        assert user_columns["account_status"]["nullable"] is False
        assert user_columns["deletion_requested_at"]["nullable"] is True
        assert user_columns["deletion_requested_at"]["type"].timezone is True
        assert user_columns["created_at"]["nullable"] is False
        assert user_columns["created_at"]["type"].timezone is True
        assert user_columns["updated_at"]["nullable"] is False
        assert user_columns["updated_at"]["type"].timezone is True

        user_unique_constraints = {
            constraint["name"] for constraint in inspector.get_unique_constraints("users")
        }
        assert "uq_users_email" in user_unique_constraints
        user_checks = {
            constraint["name"] for constraint in inspector.get_check_constraints("users")
        }
        assert user_checks == {"ck_users_account_status", "ck_users_deletion_state"}

        identity_columns = {
            column["name"]: column for column in inspector.get_columns("identities")
        }
        assert set(identity_columns) == {
            "id",
            "user_id",
            "issuer",
            "subject",
            "created_at",
            "updated_at",
        }
        assert isinstance(identity_columns["id"]["type"], Uuid)
        assert identity_columns["id"]["nullable"] is False
        assert isinstance(identity_columns["user_id"]["type"], Uuid)
        assert identity_columns["user_id"]["nullable"] is False
        assert isinstance(identity_columns["issuer"]["type"], Text)
        assert isinstance(identity_columns["subject"]["type"], Text)
        assert identity_columns["issuer"]["nullable"] is False
        assert identity_columns["subject"]["nullable"] is False
        assert identity_columns["created_at"]["nullable"] is False
        assert identity_columns["created_at"]["type"].timezone is True
        assert identity_columns["updated_at"]["nullable"] is False
        assert identity_columns["updated_at"]["type"].timezone is True

        identity_unique_constraints = {
            constraint["name"] for constraint in inspector.get_unique_constraints("identities")
        }
        assert identity_unique_constraints == {"uq_identities_issuer_subject"}
        foreign_keys = inspector.get_foreign_keys("identities")
        assert len(foreign_keys) == 1
        assert foreign_keys[0]["referred_table"] == "users"
        assert foreign_keys[0]["referred_columns"] == ["id"]
        assert foreign_keys[0]["options"]["ondelete"] == "CASCADE"
        identity_indexes = {index["name"] for index in inspector.get_indexes("identities")}
        assert "ix_identities_user_id" in identity_indexes

        command.upgrade(alembic_config, "head")

        inspector = inspect(engine)
        assert {"users", "identities", "web_sessions", "login_transactions"}.issubset(
            inspector.get_table_names()
        )

        web_session_columns = {
            column["name"]: column for column in inspector.get_columns("web_sessions")
        }
        assert set(web_session_columns) == {
            "id",
            "user_id",
            "identity_id",
            "session_token_hash",
            "csrf_token_hash",
            "created_at",
            "last_used_at",
            "idle_expires_at",
            "absolute_expires_at",
            "revoked_at",
        }
        for column_name in ("id", "user_id", "identity_id"):
            assert isinstance(web_session_columns[column_name]["type"], Uuid)
            assert web_session_columns[column_name]["nullable"] is False
        for column_name in ("session_token_hash", "csrf_token_hash"):
            assert isinstance(web_session_columns[column_name]["type"], LargeBinary)
            assert web_session_columns[column_name]["nullable"] is False
        for column_name in (
            "created_at",
            "last_used_at",
            "idle_expires_at",
            "absolute_expires_at",
        ):
            assert web_session_columns[column_name]["nullable"] is False
            assert web_session_columns[column_name]["type"].timezone is True
        assert web_session_columns["revoked_at"]["nullable"] is True
        assert web_session_columns["revoked_at"]["type"].timezone is True

        web_session_uniques = {
            constraint["name"] for constraint in inspector.get_unique_constraints("web_sessions")
        }
        assert web_session_uniques == {"uq_web_sessions_session_token_hash"}
        web_session_checks = {
            constraint["name"] for constraint in inspector.get_check_constraints("web_sessions")
        }
        assert web_session_checks == {
            "ck_web_sessions_csrf_token_hash_length",
            "ck_web_sessions_expiry_order",
            "ck_web_sessions_revocation_time",
            "ck_web_sessions_session_token_hash_length",
        }
        web_session_foreign_keys = {
            tuple(foreign_key["constrained_columns"]): foreign_key
            for foreign_key in inspector.get_foreign_keys("web_sessions")
        }
        assert set(web_session_foreign_keys) == {("user_id",), ("identity_id", "user_id")}
        assert web_session_foreign_keys[("user_id",)]["referred_table"] == "users"
        assert web_session_foreign_keys[("user_id",)]["referred_columns"] == ["id"]
        assert web_session_foreign_keys[("user_id",)]["options"]["ondelete"] == "CASCADE"
        assert web_session_foreign_keys[("identity_id", "user_id")]["referred_table"] == (
            "identities"
        )
        assert web_session_foreign_keys[("identity_id", "user_id")]["referred_columns"] == [
            "id",
            "user_id",
        ]
        assert (
            web_session_foreign_keys[("identity_id", "user_id")]["options"]["ondelete"] == "CASCADE"
        )
        web_session_indexes = {index["name"] for index in inspector.get_indexes("web_sessions")}
        assert {
            "ix_web_sessions_absolute_expires_at",
            "ix_web_sessions_identity_id",
            "ix_web_sessions_user_id",
        }.issubset(web_session_indexes)

        identity_unique_constraints = {
            constraint["name"] for constraint in inspector.get_unique_constraints("identities")
        }
        assert identity_unique_constraints == {
            "uq_identities_id_user_id",
            "uq_identities_issuer_subject",
        }

        login_transaction_columns = {
            column["name"]: column for column in inspector.get_columns("login_transactions")
        }
        assert set(login_transaction_columns) == {
            "id",
            "browser_handle_hash",
            "state_hash",
            "nonce_hash",
            "pkce_verifier",
            "intent",
            "return_to",
            "created_at",
            "expires_at",
        }
        assert isinstance(login_transaction_columns["id"]["type"], Uuid)
        assert login_transaction_columns["id"]["nullable"] is False
        for column_name in ("browser_handle_hash", "state_hash", "nonce_hash"):
            assert isinstance(login_transaction_columns[column_name]["type"], LargeBinary)
            assert login_transaction_columns[column_name]["nullable"] is False
        assert isinstance(login_transaction_columns["pkce_verifier"]["type"], String)
        assert login_transaction_columns["pkce_verifier"]["type"].length == 128
        assert isinstance(login_transaction_columns["intent"]["type"], String)
        assert login_transaction_columns["intent"]["type"].length == 16
        assert isinstance(login_transaction_columns["return_to"]["type"], String)
        assert login_transaction_columns["return_to"]["type"].length == 2048
        for column_name in ("created_at", "expires_at"):
            assert login_transaction_columns[column_name]["nullable"] is False
            assert login_transaction_columns[column_name]["type"].timezone is True

        login_transaction_uniques = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("login_transactions")
        }
        assert login_transaction_uniques == {
            "uq_login_transactions_browser_handle_hash",
            "uq_login_transactions_state_hash",
        }
        login_transaction_checks = {
            constraint["name"]: constraint["sqltext"]
            for constraint in inspector.get_check_constraints("login_transactions")
        }
        assert set(login_transaction_checks) == {
            "ck_login_transactions_browser_handle_hash_length",
            "ck_login_transactions_expiry_order",
            "ck_login_transactions_intent",
            "ck_login_transactions_nonce_hash_length",
            "ck_login_transactions_pkce_verifier_length",
            "ck_login_transactions_state_hash_length",
        }
        intent_check = login_transaction_checks["ck_login_transactions_intent"].lower()
        assert "login" in intent_check
        assert "signup" in intent_check
        assert "reauth" not in intent_check
        login_transaction_indexes = {
            index["name"] for index in inspector.get_indexes("login_transactions")
        }
        assert "ix_login_transactions_expires_at" in login_transaction_indexes

        command.check(alembic_config)
        command.downgrade(alembic_config, "20260830_0001")

        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        assert {"users", "identities"}.issubset(table_names)
        assert "web_sessions" not in table_names
        assert "login_transactions" not in table_names

        command.upgrade(alembic_config, "head")
        assert {"users", "identities", "web_sessions", "login_transactions"}.issubset(
            inspect(engine).get_table_names()
        )

        command.downgrade(alembic_config, "base")
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        assert "users" not in table_names
        assert "identities" not in table_names
        assert "web_sessions" not in table_names
        assert "login_transactions" not in table_names
        with engine.connect() as connection:
            account_status_types = connection.execute(
                text("SELECT typname FROM pg_type WHERE typname = 'account_status'")
            ).scalars()
            assert list(account_status_types) == []

        command.upgrade(alembic_config, "head")
        assert {"users", "identities", "web_sessions", "login_transactions"}.issubset(
            inspect(engine).get_table_names()
        )
    finally:
        engine.dispose()
        command.downgrade(alembic_config, "base")
