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


def test_openapi_exposes_only_the_phase_one_health_endpoint() -> None:
    assert set(app.openapi()["paths"]) == {"/health"}
