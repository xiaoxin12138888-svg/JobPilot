from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import sessionmaker

from jobpilot_api.domain.resume_imports import ResumeProfileImportPatch
from jobpilot_api.domain.resume_versions import ResumeVersionDraft
from jobpilot_api.infrastructure.database.engine import create_database_engine, sqlite_database_url
from jobpilot_api.infrastructure.database.models import ResumeVersionModel
from jobpilot_api.infrastructure.database.repositories import SqlAlchemyResumeImportRepository


def test_resume_and_profile_confirm_rolls_back_both_when_profile_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "jobpilot.db"
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())
    command.upgrade(config, "head")
    engine = create_database_engine(database_path)
    sessions = sessionmaker(engine, expire_on_commit=False)
    repository = SqlAlchemyResumeImportRepository(sessions)
    patch = ResumeProfileImportPatch.create(
        personal={"name": "示例用户"}, education=[], experience=[], links={}
    )

    def fail_profile_write(_draft):
        raise RuntimeError("forced profile failure")

    monkeypatch.setattr(
        "jobpilot_api.infrastructure.database.repositories._autofill_profile_draft_values",
        fail_profile_write,
    )

    with pytest.raises(RuntimeError, match="forced profile failure"):
        repository.confirm(
            ResumeVersionDraft.create(name="不应保存", content="不应保存的正文"), patch
        )

    with sessions() as session:
        assert session.query(ResumeVersionModel).count() == 0
    engine.dispose()
