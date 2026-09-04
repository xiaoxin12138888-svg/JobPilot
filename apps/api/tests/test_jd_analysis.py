from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from jobpilot_api.application.providers import JDAnalysisProvider
from jobpilot_api.config import ApiSettings
from jobpilot_api.domain.errors import AnalysisProviderUnavailableError
from jobpilot_api.domain.jd_analysis import JDAnalysisInput
from jobpilot_api.infrastructure.database.engine import sqlite_database_url
from jobpilot_api.main import create_app

VALID_ANALYSIS = """{
  "summary": "负责 AI 产品设计与需求分析",
  "responsibilities": [
    {"text": "负责产品设计", "evidence": "负责 AI 产品设计"}
  ],
  "mustHaveRequirements": [
    {"text": "具备需求分析能力", "evidence": "需求分析"}
  ],
  "preferredRequirements": [],
  "skills": ["AI 产品设计", "需求分析"],
  "experienceRequirements": [],
  "educationRequirements": [],
  "domainKeywords": ["AI 产品"],
  "interviewFocus": [
    {"text": "说明产品设计方法", "evidence": "AI 产品设计"}
  ]
}"""


class FakeProvider(JDAnalysisProvider):
    def __init__(self, response: str = VALID_ANALYSIS) -> None:
        self.response = response
        self.calls: list[tuple[JDAnalysisInput, str]] = []
        self.error: Exception | None = None

    def analyze(self, analysis_input: JDAnalysisInput, *, system_instruction: str) -> str:
        self.calls.append((analysis_input, system_instruction))
        if self.error is not None:
            raise self.error
        return self.response


@pytest.fixture
def analysis_context(tmp_path: Path) -> Iterator[tuple[TestClient, FakeProvider, Path]]:
    database_path = tmp_path / "jobpilot.db"
    _upgrade(database_path)
    provider = FakeProvider()
    application = create_app(
        ApiSettings.from_environment({}),
        database_path=database_path,
        analysis_provider=provider,
    )
    with TestClient(application, base_url="http://127.0.0.1") as client:
        yield client, provider, database_path


def test_analysis_create_get_and_minimal_provider_input(
    analysis_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, _database_path = analysis_context
    job = _create_job(client)

    before = client.get(f"/api/v1/jobs/{job['id']}/analysis")
    created = client.post(f"/api/v1/jobs/{job['id']}/analysis", json={})
    loaded = client.get(f"/api/v1/jobs/{job['id']}/analysis")

    assert before.status_code == 200
    assert before.json() == {"isConfigured": True, "analysis": None}
    assert created.status_code == 200
    assert created.json()["analysis"]["isStale"] is False
    assert created.json()["analysis"]["schemaVersion"] == 1
    assert created.json()["analysis"]["result"]["skills"] == ["AI 产品设计", "需求分析"]
    assert loaded.json() == created.json()
    assert len(provider.calls) == 1
    analysis_input, system_instruction = provider.calls[0]
    assert analysis_input.as_provider_data() == {
        "title": "AI 产品经理实习生",
        "company": "测试公司",
        "description": "负责 AI 产品设计与需求分析",
        "location": "上海",
        "salaryText": "200-300/天",
    }
    assert "notes" not in analysis_input.as_provider_data()
    assert "不可信" in system_instruction
    assert "忽略" in system_instruction


def test_reanalysis_updates_one_record_and_description_change_marks_stale(
    analysis_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, database_path = analysis_context
    job = _create_job(client)
    first = client.post(f"/api/v1/jobs/{job['id']}/analysis", json={}).json()["analysis"]

    notes_only = client.patch(f"/api/v1/jobs/{job['id']}", json={"notes": "本地备注"})
    assert notes_only.status_code == 200
    assert client.get(f"/api/v1/jobs/{job['id']}/analysis").json()["analysis"]["isStale"] is False

    changed = client.patch(
        f"/api/v1/jobs/{job['id']}",
        json={"description": "负责数据产品设计与需求分析"},
    )
    assert changed.status_code == 200
    stale = client.get(f"/api/v1/jobs/{job['id']}/analysis").json()["analysis"]
    assert stale["isStale"] is True

    provider.response = VALID_ANALYSIS.replace("AI 产品", "数据产品")
    refreshed = client.post(f"/api/v1/jobs/{job['id']}/analysis", json={}).json()["analysis"]
    assert refreshed["id"] == first["id"]
    assert refreshed["isStale"] is False
    with sqlite3.connect(database_path) as connection:
        count = connection.execute("SELECT count(*) FROM jd_analysis_records").fetchone()[0]
    assert count == 1


def test_invalid_reanalysis_never_overwrites_last_valid_result(
    analysis_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, _database_path = analysis_context
    job = _create_job(client)
    original = client.post(f"/api/v1/jobs/{job['id']}/analysis", json={}).json()
    provider.response = '{"summary":"missing fields"}'

    failed = client.post(f"/api/v1/jobs/{job['id']}/analysis", json={})
    loaded = client.get(f"/api/v1/jobs/{job['id']}/analysis")

    assert failed.status_code == 502
    assert failed.json()["error"]["code"] == "AI_INVALID_RESPONSE"
    assert "missing fields" not in failed.text
    assert loaded.json() == original


def test_provider_failure_is_sanitized_and_does_not_block_job_crud(
    analysis_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, _database_path = analysis_context
    job = _create_job(client)
    provider.error = AnalysisProviderUnavailableError("AI 分析暂时不可用，请稍后重试")

    failed = client.post(f"/api/v1/jobs/{job['id']}/analysis", json={})

    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "AI_PROVIDER_UNAVAILABLE"
    assert client.get(f"/api/v1/jobs/{job['id']}").status_code == 200
    assert (
        client.post("/api/v1/jobs", json={"title": "另一岗位", "company": "另一公司"}).status_code
        == 201
    )


def test_unconfigured_ai_and_empty_description_degrade_without_blocking_startup(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "jobpilot.db"
    _upgrade(database_path)
    application = create_app(ApiSettings.from_environment({}), database_path=database_path)
    with TestClient(application, base_url="http://127.0.0.1") as client:
        job = _create_job(client)
        empty_job = client.post(
            "/api/v1/jobs", json={"title": "无 JD 岗位", "company": "测试公司"}
        ).json()

        state = client.get(f"/api/v1/jobs/{job['id']}/analysis")
        unavailable = client.post(f"/api/v1/jobs/{job['id']}/analysis", json={})

        assert state.json() == {"isConfigured": False, "analysis": None}
        assert unavailable.status_code == 503
        assert unavailable.json()["error"]["code"] == "AI_NOT_CONFIGURED"
        assert client.get(f"/api/v1/jobs/{job['id']}").status_code == 200

    configured = create_app(
        ApiSettings.from_environment({}),
        database_path=database_path,
        analysis_provider=FakeProvider(),
    )
    with TestClient(configured, base_url="http://127.0.0.1") as client:
        empty = client.post(f"/api/v1/jobs/{empty_job['id']}/analysis", json={})
        assert empty.status_code == 422
        assert empty.json()["error"]["code"] == "VALIDATION_ERROR"


def test_analysis_missing_job_strict_body_and_write_origin_security(
    analysis_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, _provider, _database_path = analysis_context
    job = _create_job(client)

    assert client.get("/api/v1/jobs/missing/analysis").status_code == 404
    assert client.post("/api/v1/jobs/missing/analysis", json={}).status_code == 404
    assert (
        client.post(f"/api/v1/jobs/{job['id']}/analysis", json={"extra": True}).status_code == 422
    )
    extension = client.post(
        f"/api/v1/jobs/{job['id']}/analysis",
        headers={
            "Origin": "chrome-extension://lgchonbleblfegkckndaaandoaekmgjf",
            "Sec-Fetch-Site": "none",
        },
        json={},
    )
    cross_site = client.post(
        f"/api/v1/jobs/{job['id']}/analysis",
        headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
        json={},
    )
    web = client.post(
        f"/api/v1/jobs/{job['id']}/analysis",
        headers={"Origin": "http://127.0.0.1:5173", "Sec-Fetch-Site": "same-site"},
        json={},
    )
    assert extension.status_code == 403
    assert cross_site.status_code == 403
    assert web.status_code == 200


def test_analysis_persists_across_restart_and_cascades_with_job(tmp_path: Path) -> None:
    database_path = tmp_path / "jobpilot.db"
    _upgrade(database_path)
    first_app = create_app(
        ApiSettings.from_environment({}),
        database_path=database_path,
        analysis_provider=FakeProvider(),
    )
    with TestClient(first_app, base_url="http://127.0.0.1") as client:
        job = _create_job(client)
        expected = client.post(f"/api/v1/jobs/{job['id']}/analysis", json={}).json()

    restarted_app = create_app(
        ApiSettings.from_environment({}),
        database_path=database_path,
        analysis_provider=FakeProvider(),
    )
    with TestClient(restarted_app, base_url="http://127.0.0.1") as client:
        assert client.get(f"/api/v1/jobs/{job['id']}/analysis").json() == expected
        assert client.delete(f"/api/v1/jobs/{job['id']}").status_code == 204

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT count(*) FROM jd_analysis_records").fetchone()[0] == 0


def _create_job(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/jobs",
        json={
            "title": "AI 产品经理实习生",
            "company": "测试公司",
            "location": "上海",
            "salaryText": "200-300/天",
            "source": "manual",
            "description": "负责 AI 产品设计与需求分析",
            "notes": "绝不能发送的本地备注",
        },
    )
    assert response.status_code == 201
    return response.json()


def _upgrade(database_path: Path) -> None:
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())
    command.upgrade(config, "head")
