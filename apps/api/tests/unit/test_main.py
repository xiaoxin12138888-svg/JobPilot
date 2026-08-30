from __future__ import annotations

import httpx2
import pytest
from fastapi.testclient import TestClient

import jobpilot_api.main as main_module
from jobpilot_api.config import ApiSettings, AuthSettings
from jobpilot_api.main import create_app


def _configured_settings() -> ApiSettings:
    return ApiSettings(
        environment="test",
        cors_origins=(),
        auth=AuthSettings(
            issuer="https://tenant.example.invalid/",
            jwks_url="https://tenant.example.invalid/.well-known/jwks.json",
            authorize_url="https://tenant.example.invalid/authorize",
            token_url="https://tenant.example.invalid/oauth/token",
            audience="https://api.jobpilot.example.invalid",
            extension_client_id="extension-client-id",
            web_client_id="web-client-id",
            web_client_secret="web-client-secret",
            web_origin="https://api.jobpilot.example.invalid",
            web_callback_url=("https://api.jobpilot.example.invalid/api/v1/auth/web/callback"),
            access_token_email_claim="https://jobpilot.example.invalid/claims/email",
            access_token_email_verified_claim=(
                "https://jobpilot.example.invalid/claims/email_verified"
            ),
        ),
        database_url="postgresql+psycopg://localhost/jobpilot_lifespan_test",
    )


class CloseTrackingTransport(httpx2.BaseTransport):
    def __init__(self) -> None:
        self.closed = False

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(500, request=request)

    def close(self) -> None:
        self.closed = True


class DisposeTrackingEngine:
    def __init__(self) -> None:
        self.disposed = False

    def dispose(self) -> None:
        self.disposed = True


def test_lifespan_closes_the_auth_http_transport() -> None:
    transport = CloseTrackingTransport()
    app = create_app(_configured_settings(), auth_transport=transport)

    with TestClient(app):
        assert transport.closed is False
        assert app.state.auth_runtime is not None

    assert transport.closed is True
    assert app.state.auth_runtime is None


def test_lifespan_disposes_engine_when_http_client_initialization_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = DisposeTrackingEngine()

    def fail_http_client(*args: object, **kwargs: object) -> None:
        raise RuntimeError("HTTP client initialization failed")

    monkeypatch.setattr(main_module, "create_database_engine", lambda url: engine)
    monkeypatch.setattr(main_module.httpx2, "Client", fail_http_client)
    app = create_app(_configured_settings())

    with pytest.raises(RuntimeError, match="HTTP client initialization failed"):
        with TestClient(app):
            pass

    assert engine.disposed is True
    assert app.state.auth_runtime is None
