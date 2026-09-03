from fastapi.testclient import TestClient

from jobpilot_api.config import ApiSettings
from jobpilot_api.main import create_app


def test_cors_allows_only_the_configured_exact_origin_without_credentials() -> None:
    origin = "http://127.0.0.1:5173"
    client = TestClient(create_app(ApiSettings.from_environment({"JOBPILOT_CORS_ORIGINS": origin})))

    allowed = client.get("/health", headers={"Origin": origin})
    near_miss = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )

    assert allowed.headers["access-control-allow-origin"] == origin
    assert "access-control-allow-credentials" not in allowed.headers
    assert "access-control-allow-origin" not in near_miss.headers


def test_cors_preflight_is_get_only_and_credential_free() -> None:
    origin = "http://127.0.0.1:5173"
    client = TestClient(create_app(ApiSettings.from_environment({"JOBPILOT_CORS_ORIGINS": origin})))

    response = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Accept",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-methods"] == "GET"
    assert "access-control-allow-credentials" not in response.headers
    assert "authorization" not in response.headers["access-control-allow-headers"].lower()
    assert "x-csrf-token" not in response.headers["access-control-allow-headers"].lower()
