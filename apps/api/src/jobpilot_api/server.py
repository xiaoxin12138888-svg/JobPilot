from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import uvicorn

from jobpilot_api.config import ApiSettings
from jobpilot_api.infrastructure.database.engine import DEFAULT_DATABASE_PATH, initialize_database


def run(
    environment: Mapping[str, str] | None = None,
    *,
    reload: bool = False,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> None:
    settings = ApiSettings.from_environment(environment)
    initialize_database(database_path)
    uvicorn.run(
        "jobpilot_api.main:app",
        host=settings.bind_host,
        port=8000,
        reload=reload,
    )
