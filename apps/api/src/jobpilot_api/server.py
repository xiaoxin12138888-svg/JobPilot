from __future__ import annotations

from collections.abc import Mapping

import uvicorn

from jobpilot_api.config import ApiSettings


def run(
    environment: Mapping[str, str] | None = None,
    *,
    reload: bool = False,
) -> None:
    settings = ApiSettings.from_environment(environment)
    uvicorn.run(
        "jobpilot_api.main:app",
        host=settings.bind_host,
        port=8000,
        reload=reload,
    )
