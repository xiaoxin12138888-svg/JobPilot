from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

import jobpilot_api.infrastructure.database.engine as engine_module
from jobpilot_api.config import ApiSettings
from jobpilot_api.infrastructure.database.engine import sqlite_database_url
from jobpilot_api.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    database_path = tmp_path / "jobpilot.db"
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())
    command.upgrade(config, "head")
    application = create_app(ApiSettings.from_environment({}), database_path=database_path)
    with TestClient(application, base_url="http://127.0.0.1") as active_client:
        yield active_client


def test_job_crud_search_and_application_status_filter(client: TestClient) -> None:
    created = _create_job(client)
    second = _create_job(
        client,
        title="后端工程师",
        company="另一家公司",
        source_url=None,
    )

    response = client.get("/api/v1/jobs", params={"keyword": "测试公司"})
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == created["id"]
    assert response.json()["items"][0]["applicationStatus"] is None

    detail = client.get(f"/api/v1/jobs/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["description"] == "负责 AI 产品设计与需求分析"

    updated = client.patch(
        f"/api/v1/jobs/{created['id']}",
        json={"notes": "已准备作品集", "location": "上海 / 远程"},
    )
    assert updated.status_code == 200
    assert updated.json()["notes"] == "已准备作品集"

    application = client.post(f"/api/v1/jobs/{created['id']}/application", json={})
    assert application.status_code == 201
    assert application.json()["status"] == "planned"

    filtered = client.get("/api/v1/jobs", params={"applicationStatus": "planned"})
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == [created["id"]]

    assert client.delete(f"/api/v1/jobs/{created['id']}").status_code == 204
    assert client.get(f"/api/v1/jobs/{created['id']}").status_code == 404
    assert client.get(f"/api/v1/applications/{application.json()['id']}").status_code == 404
    assert client.get(f"/api/v1/jobs/{second['id']}").status_code == 200


def test_duplicate_normalized_source_url_is_a_conflict(client: TestClient) -> None:
    existing = _create_job(client, source_url="HTTPS://Example.com:443/jobs/1#top")

    duplicate = _create_job_response(client, source_url="https://example.COM/jobs/1")

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_JOB_URL"
    assert duplicate.json()["error"]["resourceId"] == existing["id"]
    assert "sqlite" not in duplicate.text.lower()


def test_boss_job_uses_the_existing_job_api_without_creating_an_application(
    client: TestClient,
) -> None:
    created = _create_job(
        client,
        source="boss",
        source_url="https://www.zhipin.com/job_detail/fixture123.html",
    )

    assert created["source"] == "boss"
    filtered = client.get("/api/v1/jobs", params={"source": "boss"})
    assert [item["id"] for item in filtered.json()["items"]] == [created["id"]]
    applications = client.get("/api/v1/applications", params={"jobId": created["id"]})
    assert applications.json()["total"] == 0


def test_boss_tracking_queries_are_not_stored_and_deduplicate_to_the_job_path(
    client: TestClient,
) -> None:
    canonical_url = "https://www.zhipin.com/job_detail/fixture123.html"
    existing = _create_job(
        client,
        source="boss",
        source_url=f"{canonical_url}?ka=search_list_jname&sessionId=do-not-store#apply",
    )

    duplicate = _create_job_response(
        client,
        source="boss",
        source_url=f"{canonical_url}?track=another-entry&sessionId=also-private",
    )
    stored = client.get(f"/api/v1/jobs/{existing['id']}")

    assert existing["sourceUrl"] == canonical_url
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_JOB_URL"
    assert duplicate.json()["error"]["resourceId"] == existing["id"]
    assert stored.json()["sourceUrl"] == canonical_url
    assert "sessionId" not in stored.text


def test_job_validation_and_pagination_are_bounded(client: TestClient) -> None:
    invalid = _create_job_response(client, title="   ")
    too_large = client.get("/api/v1/jobs", params={"limit": 101})

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
    assert too_large.status_code == 422
    assert "detail" not in too_large.json()


def test_job_api_stores_untrusted_job_fields_as_sanitized_plain_text(client: TestClient) -> None:
    created = _create_job(
        client,
        title="\x00 产品\x1f经理",
        company="公\x7f司",
        source_url=None,
    )

    assert created["title"] == "产品经理"
    assert created["company"] == "公司"


def test_application_lifecycle_requires_confirmation_and_rejects_invalid_jump(
    client: TestClient,
) -> None:
    job = _create_job(client)
    created = client.post(f"/api/v1/jobs/{job['id']}/application", json={})
    application_id = created.json()["id"]

    duplicate = client.post(f"/api/v1/jobs/{job['id']}/application", json={})
    unconfirmed = client.patch(
        f"/api/v1/applications/{application_id}",
        json={"status": "applied", "confirmApplied": False},
    )
    invalid_jump = client.patch(
        f"/api/v1/applications/{application_id}",
        json={"status": "offer", "confirmApplied": False},
    )
    applied = client.patch(
        f"/api/v1/applications/{application_id}",
        json={"status": "applied", "confirmApplied": True},
    )
    interviewing = client.patch(
        f"/api/v1/applications/{application_id}",
        json={"status": "interviewing", "confirmApplied": False},
    )
    offer = client.patch(
        f"/api/v1/applications/{application_id}",
        json={"status": "offer", "confirmApplied": False},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "APPLICATION_ALREADY_EXISTS"
    assert unconfirmed.status_code == 422
    assert unconfirmed.json()["error"]["code"] == "VALIDATION_ERROR"
    assert invalid_jump.status_code == 422
    assert invalid_jump.json()["error"]["code"] == "INVALID_APPLICATION_TRANSITION"
    assert applied.json()["appliedAt"] is not None
    assert interviewing.json()["status"] == "interviewing"
    assert offer.json()["status"] == "offer"

    applications = client.get("/api/v1/applications", params={"status": "offer"})
    assert applications.status_code == 200
    assert applications.json()["total"] == 1
    assert applications.json()["items"][0]["jobTitle"] == "AI 产品经理实习生"


def test_application_requires_an_existing_job(client: TestClient) -> None:
    response = client.post("/api/v1/jobs/missing/application", json={})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_application_list_filters_by_job_id(client: TestClient) -> None:
    target_job = _create_job(client, source_url=None)
    other_job = _create_job(
        client,
        title="后端工程师",
        company="另一家公司",
        source_url=None,
    )
    target_application = client.post(
        f"/api/v1/jobs/{target_job['id']}/application",
        json={},
    ).json()
    client.post(f"/api/v1/jobs/{other_job['id']}/application", json={})

    response = client.get(
        "/api/v1/applications",
        params={"jobId": target_job["id"], "limit": 1},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["id"] for item in response.json()["items"]] == [target_application["id"]]


def test_browser_writes_reject_cross_site_origin_and_non_json_body(client: TestClient) -> None:
    cross_site = client.post(
        "/api/v1/jobs",
        headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
        json={"title": "岗位", "company": "公司"},
    )
    non_json = client.post(
        "/api/v1/jobs",
        headers={"Content-Type": "text/plain"},
        content='{"title":"岗位","company":"公司"}',
    )

    assert cross_site.status_code == 403
    assert cross_site.json()["error"]["code"] == "LOCAL_WRITE_FORBIDDEN"
    assert non_json.status_code == 415
    assert non_json.json()["error"]["code"] == "JSON_REQUIRED"


def test_browser_write_accepts_exact_jobpilot_extension_origin_with_none_fetch_site(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/jobs",
        headers={
            "Origin": "chrome-extension://lgchonbleblfegkckndaaandoaekmgjf",
            "Sec-Fetch-Site": "none",
        },
        json={"title": "岗位", "company": "公司"},
    )

    assert response.status_code == 201


@pytest.mark.parametrize(
    "origin",
    [
        "chrome-extension://abcdefghijklmnopabcdefghijklmnop",
        "chrome-extension://not-a-valid-extension-id",
    ],
)
def test_browser_writes_reject_other_or_malformed_extension_origins(
    client: TestClient, origin: str
) -> None:
    response = client.post(
        "/api/v1/jobs",
        headers={"Origin": origin, "Sec-Fetch-Site": "none"},
        json={"title": "岗位", "company": "公司"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "LOCAL_WRITE_FORBIDDEN"


@pytest.mark.parametrize("fetch_site", [None, "same-origin", "same-site", "cross-site"])
def test_browser_writes_require_none_fetch_site_for_jobpilot_extension(
    client: TestClient, fetch_site: str | None
) -> None:
    headers = {"Origin": "chrome-extension://lgchonbleblfegkckndaaandoaekmgjf"}
    if fetch_site is not None:
        headers["Sec-Fetch-Site"] = fetch_site
    response = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={"title": "岗位", "company": "公司"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "LOCAL_WRITE_FORBIDDEN"


def test_browser_write_preserves_allowed_loopback_web_origin(client: TestClient) -> None:
    response = client.post(
        "/api/v1/jobs",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Sec-Fetch-Site": "same-site",
        },
        json={"title": "岗位", "company": "公司"},
    )

    assert response.status_code == 201


def test_jobpilot_extension_origin_cannot_mutate_other_api_resources(
    client: TestClient,
) -> None:
    job = _create_job(client, source_url=None)

    response = client.post(
        f"/api/v1/jobs/{job['id']}/application",
        headers={
            "Origin": "chrome-extension://lgchonbleblfegkckndaaandoaekmgjf",
            "Sec-Fetch-Site": "none",
        },
        json={},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "LOCAL_WRITE_FORBIDDEN"


def test_writes_reject_a_non_loopback_host(client: TestClient) -> None:
    response = client.post(
        "/api/v1/jobs",
        headers={"Host": "example.com", "Content-Type": "application/json"},
        json={"title": "岗位", "company": "公司"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "LOCAL_WRITE_FORBIDDEN"


def test_sqlite_busy_is_a_bounded_public_503(monkeypatch, tmp_path: Path) -> None:
    database_path = tmp_path / "busy" / "jobpilot.db"
    database_path.parent.mkdir(parents=True)
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())
    command.upgrade(config, "head")
    monkeypatch.setattr(engine_module, "SQLITE_BUSY_TIMEOUT_MILLISECONDS", 10)
    application = create_app(ApiSettings.from_environment({}), database_path=database_path)

    with (
        sqlite3.connect(database_path) as locked,
        TestClient(
            application,
            base_url="http://127.0.0.1",
        ) as busy_client,
    ):
        locked.execute("BEGIN EXCLUSIVE")
        response = _create_job_response(busy_client)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_BUSY"
    assert "sqlite" not in response.text.lower()
    assert "locked" not in response.text.lower()


def _create_job(
    client: TestClient,
    *,
    title: str = "AI 产品经理实习生",
    company: str = "测试公司",
    source: str = "manual",
    source_url: str | None = "https://example.com/jobs/ai-pm",
) -> dict[str, object]:
    response = _create_job_response(
        client,
        title=title,
        company=company,
        source=source,
        source_url=source_url,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_job_response(
    client: TestClient,
    *,
    title: str = "AI 产品经理实习生",
    company: str = "测试公司",
    source: str = "manual",
    source_url: str | None = "https://example.com/jobs/ai-pm",
):
    return client.post(
        "/api/v1/jobs",
        json={
            "title": title,
            "company": company,
            "location": "上海",
            "salaryText": "200-300/天",
            "source": source,
            "sourceUrl": source_url,
            "description": "负责 AI 产品设计与需求分析",
            "notes": "",
        },
    )
