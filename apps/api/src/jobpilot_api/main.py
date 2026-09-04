from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from jobpilot_api.api.access_log import install_uvicorn_access_query_redaction
from jobpilot_api.api.dependencies import ServiceProvider
from jobpilot_api.api.errors import install_error_handlers, install_response_header_middleware
from jobpilot_api.api.routes import router as business_router
from jobpilot_api.api.security import install_local_write_middleware
from jobpilot_api.application.providers import JDAnalysisProvider
from jobpilot_api.config import ApiSettings
from jobpilot_api.infrastructure.database.engine import DEFAULT_DATABASE_PATH


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["jobpilot-api"] = "jobpilot-api"


def create_app(
    settings: ApiSettings | None = None,
    *,
    database_path: Path = DEFAULT_DATABASE_PATH,
    analysis_provider: JDAnalysisProvider | None = None,
) -> FastAPI:
    install_uvicorn_access_query_redaction()
    active_settings = settings or ApiSettings.from_environment()
    service_provider = ServiceProvider(database_path, active_settings.llm, analysis_provider)

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        yield
        service_provider.close()

    application = FastAPI(
        title="JobPilot API",
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.state.service_provider = service_provider

    install_error_handlers(application)
    if active_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(active_settings.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Accept", "Content-Type", "X-Request-Id"],
            expose_headers=["X-Request-Id"],
        )
    install_local_write_middleware(application, active_settings)
    install_response_header_middleware(application)

    @application.get("/health", response_model=HealthResponse)
    def get_health() -> HealthResponse:
        return HealthResponse()

    application.include_router(business_router)

    return application


app = create_app()
