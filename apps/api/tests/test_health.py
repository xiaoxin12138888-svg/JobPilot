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


def test_openapi_exposes_health_and_the_current_auth_boundary() -> None:
    assert set(app.openapi()["paths"]) == {
        "/health",
        "/api/v1/auth/session",
        "/api/v1/auth/me",
        "/api/v1/auth/csrf",
        "/api/v1/auth/logout",
        "/api/v1/auth/web/authorize",
        "/api/v1/auth/web/callback",
    }


def test_openapi_documents_auth_security_and_public_error_envelopes() -> None:
    schema = app.openapi()
    assert schema["components"]["securitySchemes"]["ExtensionBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }
    web_cookie = schema["components"]["securitySchemes"]["WebSessionCookie"]
    assert web_cookie["type"] == "apiKey"
    assert web_cookie["in"] == "cookie"
    assert web_cookie["name"] == "__Host-jobpilot_session"
    assert "jobpilot_dev_session" in web_cookie["description"]
    expected_error_statuses = {
        ("/api/v1/auth/session", "post"): {400, 401, 403, 409, 422, 500, 503},
        ("/api/v1/auth/me", "get"): {400, 401, 403, 500, 503},
        ("/api/v1/auth/me", "patch"): {400, 401, 403, 422, 500, 503},
        ("/api/v1/auth/csrf", "get"): {400, 401, 500, 503},
        ("/api/v1/auth/logout", "post"): {400, 403, 422, 500, 503},
    }
    expected_security = {
        ("/api/v1/auth/session", "post"): [{"ExtensionBearer": []}],
        ("/api/v1/auth/me", "get"): [
            {"WebSessionCookie": []},
            {"ExtensionBearer": []},
        ],
        ("/api/v1/auth/me", "patch"): [
            {"WebSessionCookie": []},
            {"ExtensionBearer": []},
        ],
        ("/api/v1/auth/csrf", "get"): [{"WebSessionCookie": []}],
        ("/api/v1/auth/logout", "post"): [{}, {"WebSessionCookie": []}],
    }
    error_schema = {"$ref": "#/components/schemas/ErrorResponse"}

    for (path, method), statuses in expected_error_statuses.items():
        operation = schema["paths"][path][method]
        assert operation["security"] == expected_security[(path, method)]
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


def test_openapi_keeps_web_navigation_routes_outside_extension_bearer_security() -> None:
    schema = app.openapi()

    for path in (
        "/api/v1/auth/web/authorize",
        "/api/v1/auth/web/callback",
    ):
        operation = schema["paths"][path]["get"]
        assert operation["security"] == []


def test_openapi_documents_the_required_bounded_web_login_intent() -> None:
    schema = app.openapi()
    operation = schema["paths"]["/api/v1/auth/web/authorize"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

    assert parameters["intent"]["required"] is True
    assert parameters["intent"]["schema"]["enum"] == ["login", "signup"]
    assert parameters["returnTo"]["required"] is False
    assert "422" not in operation["responses"]
    assert "429" in operation["responses"]
    assert operation["responses"]["429"]["headers"]["Retry-After"]["schema"] == {
        "type": "integer",
        "minimum": 1,
    }


def test_openapi_callback_has_no_automatic_validation_error_contract() -> None:
    operation = app.openapi()["paths"]["/api/v1/auth/web/callback"]["get"]

    assert "422" not in operation["responses"]
    assert "503" in operation["responses"]


def test_unconfigured_auth_boundary_fails_closed_without_breaking_health() -> None:
    auth_response = client.get("/api/v1/auth/me")
    health_response = client.get("/health")

    assert auth_response.status_code == 503
    assert auth_response.json()["error"]["code"] == "SERVICE_NOT_READY"
    assert health_response.status_code == 200


def test_unconfigured_web_callback_has_a_sanitized_bootstrap_failure() -> None:
    response = client.get(
        "/api/v1/auth/web/callback",
        params={"code": "private-code", "state": "private-state"},
        follow_redirects=False,
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_NOT_READY"
    assert "location" not in response.headers
    assert "set-cookie" not in response.headers
    assert "private-code" not in response.text
    assert "private-state" not in response.text


@pytest.mark.parametrize(
    ("method", "path", "status_code", "error_code"),
    [
        ("get", "/not-a-route", 404, "RESOURCE_NOT_FOUND"),
        ("post", "/health", 405, "METHOD_NOT_ALLOWED"),
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
