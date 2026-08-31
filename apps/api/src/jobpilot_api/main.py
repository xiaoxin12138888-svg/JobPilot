from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from jobpilot_api.api.access_log import install_uvicorn_access_query_redaction
from jobpilot_api.api.errors import install_error_handlers, install_response_header_middleware
from jobpilot_api.config import ApiSettings


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["jobpilot-api"] = "jobpilot-api"


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    install_uvicorn_access_query_redaction()
    active_settings = settings or ApiSettings.from_environment()
    application = FastAPI(
        title="JobPilot API",
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )

    install_error_handlers(application)
    if active_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(active_settings.cors_origins),
            allow_credentials=False,
            allow_methods=["GET"],
            allow_headers=["Accept", "X-Request-Id"],
            expose_headers=["X-Request-Id"],
        )
    install_response_header_middleware(application)

    @application.get("/health", response_model=HealthResponse)
    def get_health() -> HealthResponse:
        return HealthResponse()

    return application


app = create_app()
