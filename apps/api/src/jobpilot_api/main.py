from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import ExitStack, asynccontextmanager
from typing import Literal

import httpx2
from fastapi import FastAPI
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from jobpilot_api.api.auth_dependencies import AuthRuntime
from jobpilot_api.api.auth_router import router as auth_router
from jobpilot_api.api.errors import (
    install_error_handlers,
    install_response_header_middleware,
)
from jobpilot_api.application.identity_service import IdentityService
from jobpilot_api.config import ApiSettings
from jobpilot_api.infrastructure.auth.access_token_validator import ExtensionAccessTokenValidator
from jobpilot_api.infrastructure.database.engine import create_database_engine
from jobpilot_api.infrastructure.database.identity_repository import SqlAlchemyIdentityUnitOfWork


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["jobpilot-api"] = "jobpilot-api"


def create_app(
    settings: ApiSettings | None = None,
    *,
    auth_transport: httpx2.BaseTransport | None = None,
) -> FastAPI:
    active_settings = settings or ApiSettings.from_environment()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.auth_runtime = None
        auth_settings = active_settings.auth
        database_url = active_settings.database_url
        if auth_settings is None or database_url is None:
            yield
            return

        with ExitStack() as resources:
            engine = create_database_engine(database_url)
            resources.callback(engine.dispose)
            http_client = httpx2.Client(
                transport=auth_transport,
                trust_env=False,
            )
            resources.callback(http_client.close)
            application.state.auth_runtime = AuthRuntime(
                access_token_validator=ExtensionAccessTokenValidator(auth_settings, http_client),
                identity_service=IdentityService(lambda: SqlAlchemyIdentityUnitOfWork(engine)),
            )
            try:
                yield
            finally:
                application.state.auth_runtime = None

    application = FastAPI(title="JobPilot API", lifespan=lifespan)
    # Keep this order: response headers wrap CORS, which wraps the error boundary.
    install_error_handlers(application)

    if active_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(active_settings.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "PATCH", "POST"],
            allow_headers=["Accept", "Authorization", "Content-Type", "X-Request-Id"],
            expose_headers=["X-Request-Id"],
        )

    install_response_header_middleware(application)

    @application.get("/health", response_model=HealthResponse)
    def get_health() -> HealthResponse:
        return HealthResponse()

    application.include_router(auth_router)

    return application


app = create_app()
