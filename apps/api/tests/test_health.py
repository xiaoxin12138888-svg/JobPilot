import pytest
from fastapi.testclient import TestClient

from jobpilot_api.main import app

client = TestClient(app)


def test_health_returns_service_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "jobpilot-api",
    }
    assert response.headers["X-Request-Id"].startswith("req_")


def test_openapi_exposes_health_and_the_current_extension_auth_boundary() -> None:
    assert set(app.openapi()["paths"]) == {
        "/health",
        "/api/v1/auth/session",
        "/api/v1/auth/me",
    }


def test_openapi_documents_auth_security_and_public_error_envelopes() -> None:
    schema = app.openapi()
    assert schema["components"]["securitySchemes"]["ExtensionBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }
    expected_error_statuses = {
        ("/api/v1/auth/session", "post"): {400, 401, 403, 409, 422, 500, 503},
        ("/api/v1/auth/me", "get"): {400, 401, 403, 500, 503},
        ("/api/v1/auth/me", "patch"): {400, 401, 403, 422, 500, 503},
    }
    error_schema = {"$ref": "#/components/schemas/ErrorResponse"}

    for (path, method), statuses in expected_error_statuses.items():
        operation = schema["paths"][path][method]
        assert operation["security"] == [{"ExtensionBearer": []}]
        for status in statuses:
            documented_schema = operation["responses"][str(status)]["content"]["application/json"][
                "schema"
            ]
            assert documented_schema == error_schema

    update_schema = schema["components"]["schemas"]["UpdateCurrentUserRequest"]
    assert update_schema["minProperties"] == 1
    assert update_schema["properties"]["locale"]["const"] == "zh-CN"
    assert update_schema["properties"]["locale"]["type"] == "string"
    assert update_schema["properties"]["timeZone"]["type"] == "string"
    assert update_schema["properties"]["timeZone"]["format"] == "iana-time-zone"
    assert "default" not in update_schema["properties"]["locale"]
    assert "default" not in update_schema["properties"]["timeZone"]
    user_id_schema = schema["components"]["schemas"]["UserView"]["properties"]["id"]
    assert user_id_schema["type"] == "string"
    assert "format" not in user_id_schema


def test_unconfigured_auth_boundary_fails_closed_without_breaking_health() -> None:
    auth_response = client.get("/api/v1/auth/me")
    health_response = client.get("/health")

    assert auth_response.status_code == 503
    assert auth_response.json()["error"]["code"] == "SERVICE_NOT_READY"
    assert health_response.status_code == 200


@pytest.mark.parametrize(
    ("method", "path", "status_code", "error_code"),
    [
        ("get", "/not-a-route", 404, "RESOURCE_NOT_FOUND"),
        ("post", "/health", 405, "BAD_REQUEST"),
    ],
)
def test_framework_http_errors_use_the_public_error_envelope(
    method: str,
    path: str,
    status_code: int,
    error_code: str,
) -> None:
    response = client.request(method, path)

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == error_code
    assert response.headers["X-Request-Id"] == response.json()["error"]["requestId"]
    assert "detail" not in response.json()
