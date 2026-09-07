from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from jobpilot_api.api.security import JOBPILOT_EXTENSION_ORIGIN
from jobpilot_api.config import ApiSettings
from jobpilot_api.infrastructure.database.engine import sqlite_database_url
from jobpilot_api.main import create_app

WEB_ORIGIN = "http://127.0.0.1:5173"
WEB_WRITE_HEADERS = {"Origin": WEB_ORIGIN, "Sec-Fetch-Site": "same-site"}
EXTENSION_READ_HEADERS = {
    "Origin": JOBPILOT_EXTENSION_ORIGIN,
    "Sec-Fetch-Site": "none",
}


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "jobpilot.db"
    _upgrade(path)
    return path


@pytest.fixture
def client(database_path: Path) -> Iterator[TestClient]:
    application = create_app(
        ApiSettings.from_environment({"JOBPILOT_CORS_ORIGINS": WEB_ORIGIN}),
        database_path=database_path,
    )
    with TestClient(application, base_url="http://127.0.0.1") as active_client:
        yield active_client


def test_profile_starts_empty_and_put_replaces_the_single_local_profile(
    client: TestClient,
) -> None:
    empty = client.get("/api/v1/autofill-profile")
    assert empty.status_code == 200
    assert empty.json() == {"profile": None}

    created = client.put(
        "/api/v1/autofill-profile",
        headers=WEB_WRITE_HEADERS,
        json=_profile_payload(name=" 示例用户\x00 "),
    )
    assert created.status_code == 200, created.text
    profile = created.json()["profile"]
    assert profile["personal"] == {
        "name": "示例用户",
        "phone": "000-0000-0000",
        "email": "candidate@example.invalid",
        "currentCity": "示例市",
    }
    assert profile["education"][0]["start"] == "2022-09"
    assert profile["experience"][0]["description"] == "梳理需求\n跟进验收。"
    assert profile["createdAt"]
    assert profile["updatedAt"]

    replaced = client.put(
        "/api/v1/autofill-profile",
        headers=WEB_WRITE_HEADERS,
        json={
            "personal": {"name": "另一位示例用户"},
            "education": [],
            "experience": [],
            "links": {},
        },
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["profile"]["personal"]["name"] == "另一位示例用户"
    assert replaced.json()["profile"]["createdAt"] == profile["createdAt"]
    assert client.get("/api/v1/autofill-profile").json() == replaced.json()


def test_profile_persists_across_api_restart(database_path: Path) -> None:
    settings = ApiSettings.from_environment({"JOBPILOT_CORS_ORIGINS": WEB_ORIGIN})
    first_app = create_app(settings, database_path=database_path)
    with TestClient(first_app, base_url="http://127.0.0.1") as first_client:
        saved = first_client.put(
            "/api/v1/autofill-profile",
            headers=WEB_WRITE_HEADERS,
            json=_profile_payload(),
        )
        assert saved.status_code == 200, saved.text

    restarted_app = create_app(settings, database_path=database_path)
    with TestClient(restarted_app, base_url="http://127.0.0.1") as restarted_client:
        loaded = restarted_client.get("/api/v1/autofill-profile")
        assert loaded.status_code == 200
        assert loaded.json() == saved.json()


def test_exact_jobpilot_extension_can_only_read_the_profile(client: TestClient) -> None:
    saved = client.put(
        "/api/v1/autofill-profile",
        headers=WEB_WRITE_HEADERS,
        json=_profile_payload(),
    )
    assert saved.status_code == 200, saved.text

    loaded = client.get("/api/v1/autofill-profile", headers=EXTENSION_READ_HEADERS)
    blocked_write = client.put(
        "/api/v1/autofill-profile",
        headers=EXTENSION_READ_HEADERS,
        json=_profile_payload(name="不应写入"),
    )

    assert loaded.status_code == 200
    assert loaded.json() == saved.json()
    assert loaded.headers["access-control-allow-origin"] == JOBPILOT_EXTENSION_ORIGIN
    assert "access-control-allow-credentials" not in loaded.headers
    assert blocked_write.status_code == 403
    assert blocked_write.json()["error"]["code"] == "LOCAL_WRITE_FORBIDDEN"


@pytest.mark.parametrize(
    ("headers", "expected_status"),
    [
        (
            {
                "Origin": "chrome-extension://abcdefghijklmnopabcdefghijklmnop",
                "Sec-Fetch-Site": "none",
            },
            403,
        ),
        ({"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"}, 403),
        (
            {"Origin": JOBPILOT_EXTENSION_ORIGIN, "Sec-Fetch-Site": "same-site"},
            403,
        ),
    ],
)
def test_profile_read_rejects_untrusted_browser_origins(
    client: TestClient, headers: dict[str, str], expected_status: int
) -> None:
    response = client.get("/api/v1/autofill-profile", headers=headers)

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == "LOCAL_READ_FORBIDDEN"


def test_profile_put_requires_json_and_domain_validation(client: TestClient) -> None:
    non_json = client.put(
        "/api/v1/autofill-profile",
        headers={**WEB_WRITE_HEADERS, "Content-Type": "text/plain"},
        content="{}",
    )
    invalid = client.put(
        "/api/v1/autofill-profile",
        headers=WEB_WRITE_HEADERS,
        json={"personal": {}, "education": [], "experience": [], "links": {}},
    )

    assert non_json.status_code == 415
    assert non_json.json()["error"]["code"] == "JSON_REQUIRED"
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"


def test_profile_read_rejects_a_non_loopback_target(client: TestClient) -> None:
    response = client.get(
        "/api/v1/autofill-profile",
        headers={**EXTENSION_READ_HEADERS, "Host": "example.com"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "LOCAL_READ_FORBIDDEN"


def _profile_payload(*, name: str = "示例用户") -> dict[str, object]:
    return {
        "personal": {
            "name": name,
            "phone": " 000-0000-0000 ",
            "email": " candidate@example.invalid ",
            "currentCity": " 示例市 ",
        },
        "education": [
            {
                "school": "示例大学",
                "major": "信息管理",
                "degree": "本科",
                "start": "2022-09",
                "end": "2026-06",
            }
        ],
        "experience": [
            {
                "company": "示例公司",
                "position": "产品实习生",
                "start": "2025-01",
                "end": "2025-06",
                "description": " 梳理需求\r\n跟进验收。 ",
            }
        ],
        "links": {
            "github": "https://github.com/example-candidate",
            "portfolio": None,
            "homepage": "https://example.invalid",
        },
    }


def _upgrade(database_path: Path) -> None:
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())
    command.upgrade(config, "head")
