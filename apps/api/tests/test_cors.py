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
    assert "x-request-id" in response.headers["access-control-expose-headers"].lower()


def test_production_defaults_to_no_cross_origin_access() -> None:
    settings = ApiSettings(environment="production", cors_origins=())
    client = TestClient(create_app(settings))

    response = client.get(
        "/health",
        headers={"Origin": "https://app.example.com"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_configured_origin_can_preflight_extension_bearer_profile_updates() -> None:
    settings = ApiSettings(
        environment="development",
        cors_origins=("chrome-extension://abcdefghijklmnop",),
    )
    client = TestClient(create_app(settings))

    response = client.options(
        "/api/v1/auth/me",
        headers={
            "Origin": "chrome-extension://abcdefghijklmnop",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "chrome-extension://abcdefghijklmnop"
    )
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    assert response.headers["X-Request-Id"].startswith("req_")


def test_configured_origin_can_read_request_id_validation_errors() -> None:
    origin = "chrome-extension://abcdefghijklmnop"
    settings = ApiSettings(
        environment="development",
        cors_origins=(origin,),
    )
    client = TestClient(create_app(settings))

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Origin": origin,
            "X-Request-Id": "invalid request id",
        },
    )

    assert response.status_code == 400
    assert response.headers["access-control-allow-origin"] == origin
    assert "x-request-id" in response.headers["access-control-expose-headers"].lower()
    assert response.headers["X-Request-Id"] == response.json()["error"]["requestId"]


def test_cors_rejects_a_wildcard_origin() -> None:
    with pytest.raises(ValueError, match="Wildcard CORS origins are not allowed"):
        ApiSettings(environment="production", cors_origins=("*",))
