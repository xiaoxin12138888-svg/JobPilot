from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from jobpilot_api.config import ApiSettings
from jobpilot_api.infrastructure.database.engine import sqlite_database_url
from jobpilot_api.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    database_path = tmp_path / "jobpilot.db"
    _upgrade(database_path)
    application = create_app(ApiSettings.from_environment({}), database_path=database_path)
    with TestClient(application, base_url="http://127.0.0.1") as active_client:
        yield active_client


def test_resume_version_crud_duplicate_and_plain_text(client: TestClient) -> None:
    created = client.post(
        "/api/v1/resume-versions",
        json={
            "name": " AI 产品经理版 ",
            "content": " 负责\x00用户需求梳理\r\n并输出 PRD。 ",
        },
    )

    assert created.status_code == 201, created.text
    resume = created.json()
    assert resume["name"] == "AI 产品经理版"
    assert resume["content"] == "负责用户需求梳理\n并输出 PRD。"
    assert resume["applicationCount"] == 0

    listed = client.get("/api/v1/resume-versions")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"] == [resume]
    assert client.get(f"/api/v1/resume-versions/{resume['id']}").json() == resume

    updated = client.patch(
        f"/api/v1/resume-versions/{resume['id']}",
        json={"name": "AI 产品经理版 V1"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "AI 产品经理版 V1"
    assert updated.json()["content"] == resume["content"]

    duplicated = client.post(
        f"/api/v1/resume-versions/{resume['id']}/duplicate",
        json={"name": "AI 产品经理版 V2"},
    )
    assert duplicated.status_code == 201
    assert duplicated.json()["id"] != resume["id"]
    assert duplicated.json()["name"] == "AI 产品经理版 V2"
    assert duplicated.json()["content"] == resume["content"]

    assert client.delete(f"/api/v1/resume-versions/{duplicated.json()['id']}").status_code == 204
    assert client.get(f"/api/v1/resume-versions/{duplicated.json()['id']}").status_code == 404


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"name": " ", "content": "正文"}, 422),
        ({"name": "版本", "content": "   "}, 422),
        ({"name": "x" * 201, "content": "正文"}, 422),
        ({"name": "版本", "content": "x" * 100_001}, 422),
    ],
)
def test_resume_version_input_is_bounded(
    client: TestClient, payload: dict[str, str], expected_status: int
) -> None:
    response = client.post("/api/v1/resume-versions", json=payload)

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_application_resume_association_is_explicit_changeable_and_clearable(
    client: TestClient,
) -> None:
    job = _create_job(client)
    first = _create_resume(client, "AI 产品经理版")
    second = _create_resume(client, "通用产品版")
    application = client.post(f"/api/v1/jobs/{job['id']}/application", json={}).json()

    assert application["resumeVersionId"] is None
    assert client.get(f"/api/v1/resume-versions/{first['id']}").json()["applicationCount"] == 0

    attached = client.patch(
        f"/api/v1/applications/{application['id']}",
        json={"resumeVersionId": first["id"]},
    )
    assert attached.status_code == 200, attached.text
    assert attached.json()["status"] == "planned"
    assert attached.json()["resumeVersionId"] == first["id"]
    assert client.get(f"/api/v1/resume-versions/{first['id']}").json()["applicationCount"] == 1

    changed = client.patch(
        f"/api/v1/applications/{application['id']}",
        json={"resumeVersionId": second["id"]},
    )
    assert changed.json()["resumeVersionId"] == second["id"]

    cleared = client.patch(
        f"/api/v1/applications/{application['id']}",
        json={"resumeVersionId": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["resumeVersionId"] is None

    invalid = client.patch(
        f"/api/v1/applications/{application['id']}",
        json={"resumeVersionId": "missing-resume"},
    )
    assert invalid.status_code == 404
    assert invalid.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_referenced_resume_cannot_be_deleted_and_association_persists_after_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "jobpilot.db"
    _upgrade(database_path)
    settings = ApiSettings.from_environment({})
    application = create_app(settings, database_path=database_path)
    with TestClient(application, base_url="http://127.0.0.1") as first_client:
        job = _create_job(first_client)
        resume = _create_resume(first_client, "AI 产品经理版")
        application_record = first_client.post(
            f"/api/v1/jobs/{job['id']}/application", json={}
        ).json()
        first_client.patch(
            f"/api/v1/applications/{application_record['id']}",
            json={"resumeVersionId": resume["id"]},
        )

        blocked = first_client.delete(f"/api/v1/resume-versions/{resume['id']}")
        assert blocked.status_code == 409
        assert blocked.json()["error"]["code"] == "RESUME_VERSION_IN_USE"

    restarted = create_app(settings, database_path=database_path)
    with TestClient(restarted, base_url="http://127.0.0.1") as second_client:
        loaded = second_client.get(f"/api/v1/applications/{application_record['id']}")
        assert loaded.status_code == 200
        assert loaded.json()["resumeVersionId"] == resume["id"]
        assert (
            second_client.get(f"/api/v1/resume-versions/{resume['id']}").json()["applicationCount"]
            == 1
        )


def _upgrade(database_path: Path) -> None:
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())
    command.upgrade(config, "head")


def _create_resume(client: TestClient, name: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/resume-versions",
        json={"name": name, "content": "负责用户需求梳理并输出 PRD。"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_job(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/jobs",
        json={
            "title": "AI 产品经理",
            "company": "示例公司",
            "description": "负责需求分析。",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
