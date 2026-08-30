from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import String, Text, Uuid, inspect, text

from jobpilot_api.infrastructure.database.engine import create_database_engine


def test_database_engine_rejects_non_postgresql_urls() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        create_database_engine("sqlite+pysqlite:///:memory:")


def test_migration_history_has_one_head(alembic_config: Config) -> None:
    script = ScriptDirectory.from_config(alembic_config)

    assert len(script.get_heads()) == 1


def test_user_identity_migration_up_down_up(
    alembic_config: Config,
    database_url: str,
) -> None:
    engine = create_database_engine(database_url)
    try:
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "head")

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

        command.check(alembic_config)
        command.downgrade(alembic_config, "base")

        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        assert "users" not in table_names
        assert "identities" not in table_names
        with engine.connect() as connection:
            account_status_types = connection.execute(
                text("SELECT typname FROM pg_type WHERE typname = 'account_status'")
            ).scalars()
            assert list(account_status_types) == []

        command.upgrade(alembic_config, "head")
        assert {"users", "identities"}.issubset(inspect(engine).get_table_names())
    finally:
        engine.dispose()
        command.downgrade(alembic_config, "base")
