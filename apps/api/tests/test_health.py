import importlib

from fastapi.testclient import TestClient

import jobpilot_api.infrastructure.database.engine as engine_module
import jobpilot_api.main as main_module
from jobpilot_api.config import ApiSettings
from jobpilot_api.main import app


def test_health_returns_service_status() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "jobpilot-api",
    }
    assert response.headers["X-Request-Id"].startswith("req_")


def test_openapi_exposes_only_health_and_approved_business_routes() -> None:
    assert set(app.openapi()["paths"]) == {
        "/health",
        "/api/v1/jobs",
        "/api/v1/jobs/{job_id}",
        "/api/v1/jobs/{job_id}/application",
        "/api/v1/jobs/{job_id}/analysis",
        "/api/v1/applications",
        "/api/v1/applications/{application_id}",
    }


def test_framework_documentation_routes_are_not_exposed() -> None:
    client = TestClient(app)

    for path in ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"):
        assert client.get(path).status_code == 404


def test_health_startup_does_not_require_or_connect_to_a_database(
    monkeypatch,
) -> None:
    def fail_database_engine(*args: object, **kwargs: object) -> None:
        raise AssertionError("health-only startup must not create a database engine")

    monkeypatch.setattr(engine_module, "create_database_engine", fail_database_engine)
    reloaded_main = importlib.reload(main_module)

    with TestClient(reloaded_main.create_app(ApiSettings.from_environment({}))) as client:
        response = client.get("/health")

    assert response.status_code == 200


def test_framework_http_errors_use_the_public_error_envelope() -> None:
    response = TestClient(app).get("/not-a-route")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert response.headers["X-Request-Id"] == response.json()["error"]["requestId"]
    assert "detail" not in response.json()
