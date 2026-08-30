from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from contextlib import ExitStack, asynccontextmanager
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Literal
from urllib.parse import urlsplit

import httpx2
from fastapi import FastAPI
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from jobpilot_api.api.access_log import install_uvicorn_access_query_redaction
from jobpilot_api.api.auth_dependencies import AuthRuntime, WebAuthRuntime
from jobpilot_api.api.auth_router import router as auth_router
from jobpilot_api.api.errors import (
    install_error_handlers,
    install_response_header_middleware,
)
from jobpilot_api.api.login_rate_limit import WebLoginRateLimiter
from jobpilot_api.api.web_auth_router import router as web_auth_router
from jobpilot_api.api.web_session_router import router as web_session_router
from jobpilot_api.application.identity_service import IdentityService
from jobpilot_api.application.web_auth_service import (
    WEB_LOGIN_ENTROPY_BYTES,
    WebAuthService,
)
from jobpilot_api.application.web_session_service import WebSessionService
from jobpilot_api.config import ApiSettings
from jobpilot_api.infrastructure.auth.access_token_validator import ExtensionAccessTokenValidator
from jobpilot_api.infrastructure.auth.auth0_web_provider import Auth0WebProvider
from jobpilot_api.infrastructure.auth.jwks import JwksResolver
from jobpilot_api.infrastructure.database.engine import create_database_engine
from jobpilot_api.infrastructure.database.identity_repository import SqlAlchemyIdentityUnitOfWork
from jobpilot_api.infrastructure.database.web_session_repository import (
    SqlAlchemyWebSessionUnitOfWork,
)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["jobpilot-api"] = "jobpilot-api"


def create_app(
    settings: ApiSettings | None = None,
    *,
    auth_transport: httpx2.BaseTransport | None = None,
) -> FastAPI:
    install_uvicorn_access_query_redaction()
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
            identity_service = IdentityService(partial(SqlAlchemyIdentityUnitOfWork, engine))
            web_session_factory = partial(SqlAlchemyWebSessionUnitOfWork, engine)
            web_session_service = WebSessionService(
                web_session_factory,
                idle_timeout=timedelta(seconds=auth_settings.web_session_idle_seconds),
                absolute_timeout=timedelta(seconds=auth_settings.web_session_absolute_seconds),
            )
            signing_key_resolver = JwksResolver(auth_settings, http_client)
            cookie_secure = urlsplit(auth_settings.web_origin).scheme == "https"
            application.state.auth_runtime = AuthRuntime(
                access_token_validator=ExtensionAccessTokenValidator(
                    auth_settings,
                    http_client,
                    signing_key_resolver=signing_key_resolver,
                ),
                identity_service=identity_service,
                web=WebAuthRuntime(
                    service=WebAuthService(
                        web_session_factory,
                        identity_service,
                        web_session_service,
                        Auth0WebProvider(
                            auth_settings,
                            http_client,
                            signing_key_resolver,
                        ),
                        token_factory=lambda: secrets.token_bytes(WEB_LOGIN_ENTROPY_BYTES),
                        clock=lambda: datetime.now(UTC),
                    ),
                    session_service=web_session_service,
                    login_rate_limiter=WebLoginRateLimiter(),
                    web_origin=auth_settings.web_origin,
                    transaction_cookie_name=(
                        "__Host-jobpilot_login_tx" if cookie_secure else "jobpilot_dev_login_tx"
                    ),
                    session_cookie_name=(
                        "__Host-jobpilot_session" if cookie_secure else "jobpilot_dev_session"
                    ),
                    cookie_secure=cookie_secure,
                    session_max_age=auth_settings.web_session_absolute_seconds,
                ),
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
            allow_credentials=True,
            allow_methods=["GET", "PATCH", "POST"],
            allow_headers=[
                "Accept",
                "Authorization",
                "Content-Type",
                "X-CSRF-Token",
                "X-Request-Id",
            ],
            expose_headers=["X-Request-Id"],
        )

    install_response_header_middleware(application)

    @application.get("/health", response_model=HealthResponse)
    def get_health() -> HealthResponse:
        return HealthResponse()

    application.include_router(auth_router)
    application.include_router(web_auth_router)
    application.include_router(web_session_router)

    return application


app = create_app()
