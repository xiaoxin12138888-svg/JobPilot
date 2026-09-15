from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from jobpilot_api.infrastructure.database.engine import sqlite_database_url


def test_copilot_schema_v2_migration_preserves_v1_and_is_reversible(tmp_path: Path) -> None:
    database_path = tmp_path / "jobpilot.db"
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())
    command.upgrade(config, "0011_copilot_records")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO jobs (id, title, company, source, created_at, updated_at)
            VALUES ('job-1', '产品经理', '示例公司', 'manual', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        connection.execute(_insert_record_sql(), _record_values("record-v1", 1))
        connection.commit()

    command.upgrade(config, "head")
    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT id, schema_version FROM copilot_records ORDER BY id"
        ).fetchall() == [("record-v1", 1)]
        connection.execute(_insert_record_sql(), _record_values("record-v2", 2))
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(_insert_record_sql(), _record_values("record-v3", 3))
        connection.rollback()

    with pytest.raises(RuntimeError, match="schema version 2 records exist"):
        command.downgrade(config, "0011_copilot_records")

    with sqlite3.connect(database_path) as connection:
        connection.execute("DELETE FROM copilot_records WHERE schema_version = 2")
        connection.commit()
    command.downgrade(config, "0011_copilot_records")
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT id, schema_version FROM copilot_records").fetchall() == [
            ("record-v1", 1)
        ]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(_insert_record_sql(), _record_values("record-v2-again", 2))


def _insert_record_sql() -> str:
    return """
        INSERT INTO copilot_records (
            id, job_id, resume_version_id, kind, schema_version, result_json,
            input_fingerprint, model, prompt_version, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """


def _record_values(record_id: str, schema_version: int) -> tuple[object, ...]:
    return (
        record_id,
        "job-1",
        None,
        "INTERVIEW_PREP",
        schema_version,
        json.dumps(
            {
                "possibleQuestions": [],
                "review": {"strengths": [], "weaknesses": [], "nextActions": []},
            }
        ),
        "a" * 64,
        "fictional-model",
        f"interview-prep-v{schema_version}",
    )
