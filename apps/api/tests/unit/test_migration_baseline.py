import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from jobpilot_api.infrastructure.database.engine import sqlite_database_url
from jobpilot_api.infrastructure.database.models import Base


def test_model_metadata_and_migration_history_contain_phase_7_resume_tables() -> None:
    config = Config("apps/api/alembic.ini")
    script = ScriptDirectory.from_config(config)

    assert set(Base.metadata.tables) == {
        "jobs",
        "applications",
        "jd_analysis_records",
        "resume_versions",
    }
    assert len(script.get_heads()) == 1


def test_alembic_connects_to_an_explicit_temporary_sqlite_database(tmp_path: Path) -> None:
    database_path = tmp_path / "migration" / "jobpilot.db"
    database_path.parent.mkdir(parents=True)
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())

    command.ensure_version(config)

    with sqlite3.connect(database_path) as connection:
        version_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'alembic_version'"
        ).fetchone()
    assert version_table == ("alembic_version",)


def test_phase_4_source_migration_preserves_phase_3_data_and_is_reversible(tmp_path: Path) -> None:
    database_path = tmp_path / "migration" / "jobpilot.db"
    database_path.parent.mkdir(parents=True)
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())

    command.upgrade(config, "0001_job_application")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                id, title, company, source, created_at, updated_at
            ) VALUES ('manual-job', '岗位', '公司', 'manual', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        connection.execute(
            """
            INSERT INTO applications (
                id, job_id, status, created_at, updated_at
            ) VALUES ('application-1', 'manual-job', 'planned', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        connection.commit()

    command.upgrade(config, "head")
    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        job_columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()}
        application_foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(applications)"
        ).fetchall()
        connection.execute(
            """
            INSERT INTO jobs (
                id, title, company, source, source_url, created_at, updated_at
            ) VALUES (
                'boss-job', '产品经理', '测试公司', 'boss',
                'https://www.zhipin.com/job_detail/fixture123.html',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """
        )
        preserved_application = connection.execute(
            "SELECT job_id, status FROM applications WHERE id = 'application-1'"
        ).fetchone()
        connection.execute("DELETE FROM jobs WHERE id = 'boss-job'")
        connection.commit()

    assert {"jobs", "applications", "alembic_version"}.issubset(tables)
    assert "normalized_source_url" in job_columns
    assert any(
        row[2] == "jobs" and row[3] == "job_id" and row[6] == "CASCADE"
        for row in application_foreign_keys
    )
    assert preserved_application == ("manual-job", "planned")

    command.downgrade(config, "0001_job_application")
    with sqlite3.connect(database_path) as connection:
        preserved_job = connection.execute(
            "SELECT source FROM jobs WHERE id = 'manual-job'"
        ).fetchone()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO jobs (
                    id, title, company, source, created_at, updated_at
                ) VALUES ('rejected-boss', '岗位', '公司', 'boss', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            )

    assert preserved_job == ("manual",)

    command.upgrade(config, "head")
    with sqlite3.connect(database_path) as connection:
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert version == ("0005_resume_versions",)


def test_source_migration_refuses_to_downgrade_while_boss_jobs_exist(tmp_path: Path) -> None:
    database_path = tmp_path / "migration" / "jobpilot.db"
    database_path.parent.mkdir(parents=True)
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())
    command.upgrade(config, "head")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                id, title, company, source, created_at, updated_at
            ) VALUES ('boss-job', '岗位', '公司', 'boss', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        connection.commit()

    with pytest.raises(RuntimeError, match="BOSS jobs exist"):
        command.downgrade(config, "0001_job_application")

    with sqlite3.connect(database_path) as connection:
        preserved = connection.execute("SELECT source FROM jobs WHERE id = 'boss-job'").fetchone()
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert preserved == ("boss",)
    assert version == ("0002_boss_job_source",)


def test_phase_5_source_migration_preserves_existing_data_and_is_reversible(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration" / "jobpilot.db"
    database_path.parent.mkdir(parents=True)
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())
    command.upgrade(config, "0002_boss_job_source")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                id, title, company, source, created_at, updated_at
            ) VALUES ('boss-job', '岗位', '公司', 'boss', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        connection.execute(
            """
            INSERT INTO applications (
                id, job_id, status, created_at, updated_at
            ) VALUES ('application-1', 'boss-job', 'planned', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        connection.commit()

    command.upgrade(config, "head")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                id, title, company, source, created_at, updated_at
            ) VALUES ('nowcoder-job', '岗位', '公司', 'nowcoder', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        preserved = connection.execute(
            """
            SELECT jobs.source, applications.status
            FROM jobs JOIN applications ON applications.job_id = jobs.id
            WHERE jobs.id = 'boss-job'
            """
        ).fetchone()
        connection.execute("DELETE FROM jobs WHERE id = 'nowcoder-job'")
        connection.commit()

    assert preserved == ("boss", "planned")
    command.downgrade(config, "0002_boss_job_source")
    command.upgrade(config, "head")

    with sqlite3.connect(database_path) as connection:
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert version == ("0005_resume_versions",)


def test_phase_5_source_migration_refuses_downgrade_while_nowcoder_jobs_exist(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration" / "jobpilot.db"
    database_path.parent.mkdir(parents=True)
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())
    command.upgrade(config, "head")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                id, title, company, source, created_at, updated_at
            ) VALUES ('nowcoder-job', '岗位', '公司', 'nowcoder', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        connection.commit()

    with pytest.raises(RuntimeError, match="Nowcoder jobs exist"):
        command.downgrade(config, "0002_boss_job_source")

    with sqlite3.connect(database_path) as connection:
        preserved = connection.execute(
            "SELECT source FROM jobs WHERE id = 'nowcoder-job'"
        ).fetchone()
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert preserved == ("nowcoder",)
    assert version == ("0003_nowcoder_job_source",)


def test_phase_6_analysis_migration_is_reversible_and_cascades(tmp_path: Path) -> None:
    database_path = tmp_path / "migration" / "jobpilot.db"
    database_path.parent.mkdir(parents=True)
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())
    command.upgrade(config, "head")

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """
            INSERT INTO jobs (id, title, company, source, created_at, updated_at)
            VALUES ('job-1', '岗位', '公司', 'manual', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        connection.execute(
            """
            INSERT INTO jd_analysis_records (
                id, job_id, schema_version, result_json, source_fingerprint,
                created_at, updated_at
            ) VALUES (
                'analysis-1', 'job-1', 1, '{}',
                'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute("DELETE FROM jobs WHERE id = 'job-1'")
        connection.commit()
        assert connection.execute("SELECT count(*) FROM jd_analysis_records").fetchone()[0] == 0

    command.downgrade(config, "0003_nowcoder_job_source")
    command.upgrade(config, "head")
    with sqlite3.connect(database_path) as connection:
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert version == ("0005_resume_versions",)


def test_phase_7_resume_migration_is_reversible_and_preserves_applications(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "phase-7-resume.db"
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())
    command.upgrade(config, "0004_jd_analysis_records")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO jobs (id, title, company, source, created_at, updated_at)
            VALUES ('job-1', '岗位', '公司', 'manual', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        connection.execute(
            """
            INSERT INTO applications (id, job_id, status, created_at, updated_at)
            VALUES ('application-1', 'job-1', 'planned', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        connection.commit()

    command.upgrade(config, "head")
    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(applications)").fetchall()
        }
        foreign_keys = connection.execute("PRAGMA foreign_key_list(applications)").fetchall()
        connection.execute(
            """
            INSERT INTO resume_versions (id, name, content, created_at, updated_at)
            VALUES ('resume-1', '版本', '虚构简历正文', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        connection.execute(
            "UPDATE applications SET resume_version_id = 'resume-1' WHERE id = 'application-1'"
        )
        connection.commit()

    assert "resume_version_id" in columns
    assert any(
        row[2] == "resume_versions" and row[3] == "resume_version_id" and row[6] == "RESTRICT"
        for row in foreign_keys
    )

    command.downgrade(config, "0004_jd_analysis_records")
    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        application = connection.execute(
            "SELECT id, job_id, status FROM applications WHERE id = 'application-1'"
        ).fetchone()
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(applications)").fetchall()
        }

    assert "resume_versions" not in tables
    assert "resume_version_id" not in columns
    assert application == ("application-1", "job-1", "planned")
