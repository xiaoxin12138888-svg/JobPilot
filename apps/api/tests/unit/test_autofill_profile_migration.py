from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from jobpilot_api.infrastructure.database.engine import sqlite_database_url
from jobpilot_api.infrastructure.database.models import Base


def test_profile_model_and_migration_have_one_head() -> None:
    config = Config("apps/api/alembic.ini")
    script = ScriptDirectory.from_config(config)

    assert "autofill_profiles" in Base.metadata.tables
    assert script.get_current_head() == "0010_profile_projects"


def test_project_migration_backfills_existing_profile_and_is_reversible(tmp_path: Path) -> None:
    database_path = tmp_path / "phase-10-profile-projects.db"
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())
    command.upgrade(config, "0009_autofill_profile")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO autofill_profiles (
                id, personal_json, education_json, experience_json, links_json,
                created_at, updated_at
            ) VALUES (1, '{"name":"示例用户"}', '[]', '[]', '{}',
                      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        connection.commit()

    command.upgrade(config, "head")
    with sqlite3.connect(database_path) as connection:
        projects_json = connection.execute(
            "SELECT projects_json FROM autofill_profiles WHERE id = 1"
        ).fetchone()
        personal_json = connection.execute(
            "SELECT personal_json FROM autofill_profiles WHERE id = 1"
        ).fetchone()

    assert projects_json == ("[]",)
    assert personal_json == ('{"name":"示例用户"}',)

    command.downgrade(config, "0009_autofill_profile")
    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(autofill_profiles)").fetchall()
        }
        preserved_personal = connection.execute(
            "SELECT personal_json FROM autofill_profiles WHERE id = 1"
        ).fetchone()

    assert "projects_json" not in columns
    assert preserved_personal == ('{"name":"示例用户"}',)


def test_profile_migration_is_singleton_reversible_and_preserves_existing_data(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "phase-9-profile.db"
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())
    command.upgrade(config, "0008_interview_feedback")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO jobs (id, title, company, source, created_at, updated_at)
            VALUES ('job-1', '虚构岗位', '虚构公司', 'manual', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        connection.commit()

    command.upgrade(config, "head")
    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(autofill_profiles)").fetchall()
        }
        connection.execute(
            """
            INSERT INTO autofill_profiles (
                id, personal_json, education_json, experience_json, links_json,
                created_at, updated_at
            ) VALUES (1, '{}', '[]', '[]', '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO autofill_profiles (
                    id, personal_json, education_json, experience_json, links_json,
                    created_at, updated_at
                ) VALUES (2, '{}', '[]', '[]', '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            )
        connection.rollback()

    assert columns == {
        "id",
        "personal_json",
        "education_json",
        "experience_json",
        "projects_json",
        "links_json",
        "created_at",
        "updated_at",
    }

    command.downgrade(config, "0008_interview_feedback")
    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        preserved_job = connection.execute("SELECT title FROM jobs WHERE id = 'job-1'").fetchone()

    assert "autofill_profiles" not in tables
    assert preserved_job == ("虚构岗位",)
