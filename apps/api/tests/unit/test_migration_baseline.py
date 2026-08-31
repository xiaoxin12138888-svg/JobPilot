from alembic.config import Config
from alembic.script import ScriptDirectory

from jobpilot_api.infrastructure.database.models import Base


def test_model_metadata_and_migration_history_are_empty() -> None:
    config = Config("apps/api/alembic.ini")
    script = ScriptDirectory.from_config(config)

    assert set(Base.metadata.tables) == set()
    assert script.get_heads() == []
