from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from jobpilot_api.config import ApiSettings


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["jobpilot-api"] = "jobpilot-api"


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    active_settings = settings or ApiSettings.from_environment()
    application = FastAPI(title="JobPilot API")

    if active_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(active_settings.cors_origins),
            allow_credentials=False,
            allow_methods=["GET"],
            allow_headers=["Accept", "Content-Type"],
        )

    @application.get("/health", response_model=HealthResponse)
    def get_health() -> HealthResponse:
        return HealthResponse()

    return application


app = create_app()
