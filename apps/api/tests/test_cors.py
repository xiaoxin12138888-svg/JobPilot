import pytest
from fastapi.testclient import TestClient

from jobpilot_api.config import ApiSettings
from jobpilot_api.main import create_app


def test_development_cors_allows_the_configured_web_origin() -> None:
    settings = ApiSettings(
        environment="development",
        cors_origins=("http://localhost:5173",),
    )
    client = TestClient(create_app(settings))

    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_production_defaults_to_no_cross_origin_access() -> None:
    settings = ApiSettings(environment="production", cors_origins=())
    client = TestClient(create_app(settings))

    response = client.get(
        "/health",
        headers={"Origin": "https://app.example.com"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_cors_rejects_a_wildcard_origin() -> None:
    with pytest.raises(ValueError, match="Wildcard CORS origins are not allowed"):
        ApiSettings(environment="production", cors_origins=("*",))
