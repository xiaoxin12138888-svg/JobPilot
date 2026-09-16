from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from jobpilot_api.application.providers import (
    CopilotProvider,
    CopilotRepairRequest,
    JDAnalysisProvider,
)
from jobpilot_api.config import ApiSettings
from jobpilot_api.domain.copilot import CopilotInput, CopilotKind
from jobpilot_api.domain.errors import AnalysisProviderUnavailableError, AnalysisTimeoutError
from jobpilot_api.domain.jd_analysis import JDAnalysisInput
from jobpilot_api.infrastructure.database.engine import sqlite_database_url
from jobpilot_api.main import create_app

VALID_ANALYSIS = json.dumps(
    {
        "summary": "AI 产品需求岗位",
        "responsibilities": [],
        "mustHaveRequirements": [
            {"text": "负责 AI 产品需求分析", "evidence": "负责 AI 产品需求分析"}
        ],
        "preferredRequirements": [],
        "skills": [],
        "experienceRequirements": [],
        "educationRequirements": [],
        "domainKeywords": [],
        "interviewFocus": [],
    },
    ensure_ascii=False,
)


class FakeProvider(JDAnalysisProvider, CopilotProvider):
    model = "fictional-model"

    def __init__(self) -> None:
        self.copilot_calls: list[tuple[CopilotInput, str, CopilotRepairRequest | None]] = []
        self.copilot_error: Exception | None = None
        self.copilot_failures: list[Exception | None] = []
        self.copilot_responses: list[str] = []

    def analyze(self, _input: JDAnalysisInput, *, system_instruction: str) -> str:
        return VALID_ANALYSIS

    def generate_copilot(
        self,
        copilot_input: CopilotInput,
        *,
        system_instruction: str,
        repair: CopilotRepairRequest | None = None,
    ) -> str:
        self.copilot_calls.append((copilot_input, system_instruction, repair))
        if self.copilot_failures:
            failure = self.copilot_failures.pop(0)
            if failure is not None:
                raise failure
        if self.copilot_error is not None:
            raise self.copilot_error
        if self.copilot_responses:
            return self.copilot_responses.pop(0)
        if copilot_input.kind == CopilotKind.RESUME_ADVICE:
            assert copilot_input.resume_source is not None
            return json.dumps(
                {
                    "highlight": [
                        {
                            "text": "突出 AI 产品需求分析实践。",
                            "sourceEvidence": {
                                "text": "参与 AI 产品需求分析",
                                "sourceType": "RESUME",
                                "sourceId": copilot_input.resume_source.id,
                            },
                        }
                    ],
                    "possibleImprovement": ["如有真实结果指标，可核实后补充。"],
                    "interviewFocus": [
                        {
                            "text": "准备需求分析方法和取舍案例。",
                            "sourceEvidence": {
                                "text": "负责 AI 产品需求分析",
                                "sourceType": "JOB",
                                "sourceId": copilot_input.job_sources[1].id,
                            },
                        }
                    ],
                },
                ensure_ascii=False,
            )
        if copilot_input.kind == CopilotKind.INTERVIEW_PREP:
            review = {"strengths": [], "weaknesses": [], "nextActions": []}
            if copilot_input.interview_sources:
                interview = copilot_input.interview_sources[0]
                review = {
                    "strengths": [
                        {
                            "text": "已记录需求分析中的良好表现。",
                            "sourceEvidence": {
                                "text": "需求分析思路清楚",
                                "sourceType": "INTERVIEW",
                                "sourceId": interview.id,
                            },
                        }
                    ],
                    "weaknesses": [
                        {
                            "text": "数据指标说明仍需加强。",
                            "sourceEvidence": {
                                "text": "数据指标回答不完整",
                                "sourceType": "INTERVIEW",
                                "sourceId": interview.id,
                            },
                        }
                    ],
                    "nextActions": ["用真实项目材料补充指标口径。"],
                }
            questions = [
                {
                    "category": category,
                    "question": f"可能关注方向：{category} 场景中的需求分析。",
                    "reason": "岗位要求负责 AI 产品需求分析。",
                    "sourceEvidence": {
                        "text": "负责 AI 产品需求分析",
                        "sourceType": "JOB",
                        "sourceId": copilot_input.job_sources[1].id,
                    },
                }
                for category in ("PRODUCT", "AI", "PROJECT")
            ]
            return json.dumps(
                {"possibleQuestions": questions, "review": review},
                ensure_ascii=False,
            )
        assert copilot_input.resume_source is not None
        return json.dumps(
            {
                "summary": "当前经历与岗位的 AI 产品需求职责存在直接对应。",
                "strengths": [
                    {
                        "text": "已有 AI 产品需求实践。",
                        "sourceEvidence": {
                            "text": "参与 AI 产品需求分析",
                            "sourceType": "RESUME",
                            "sourceId": copilot_input.resume_source.id,
                        },
                    }
                ],
                "gaps": [
                    {
                        "text": "当前简历未发现独立负责完整需求闭环的明确描述。",
                        "sourceEvidence": {
                            "text": "负责 AI 产品需求分析",
                            "sourceType": "JOB",
                            "sourceId": copilot_input.job_sources[0].id,
                        },
                    }
                ],
                "suggestions": ["准备需求分析方法与结果的具体案例。"],
            },
            ensure_ascii=False,
        )


@pytest.fixture
def copilot_context(tmp_path: Path) -> Iterator[tuple[TestClient, FakeProvider, Path]]:
    database_path = tmp_path / "jobpilot.db"
    _upgrade(database_path)
    provider = FakeProvider()
    application = create_app(
        ApiSettings.from_environment({}),
        database_path=database_path,
        analysis_provider=provider,
        copilot_provider=provider,
    )
    with TestClient(application, base_url="http://127.0.0.1") as client:
        yield client, provider, database_path


def test_match_generation_is_append_only_grounded_and_uses_minimal_redacted_input(
    copilot_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, _database_path = copilot_context
    job, resume = _create_sources(client)
    endpoint = f"/api/v1/jobs/{job['id']}/copilot/match"
    request = {"resumeVersionId": resume["id"], "confirmExternalAi": True}

    empty = client.get(endpoint, params={"resumeVersionId": resume["id"]})
    first = client.post(endpoint, json=request)
    second = client.post(endpoint, json=request)
    latest = client.get(endpoint, params={"resumeVersionId": resume["id"]})
    by_id = client.get(f"/api/v1/copilot/{first.json()['record']['id']}")

    assert empty.json() == {"isConfigured": True, "record": None}
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["record"]["id"] != second.json()["record"]["id"]
    assert latest.json() == second.json()
    assert by_id.json() == first.json()
    record = first.json()["record"]
    assert record["kind"] == "MATCH"
    assert record["schemaVersion"] == 2
    assert record["model"] == "fictional-model"
    assert record["promptVersion"] == "match-v2"
    assert record["isStale"] is False
    assert len(record["inputFingerprint"]) == 64

    provider_data = provider.copilot_calls[0][0].as_provider_data()
    serialized = json.dumps(provider_data, ensure_ascii=False)
    assert "fictional@example.com" not in serialized
    assert "138001" not in serialized
    assert "示例公司" not in serialized
    assert set(provider_data) == {"task", "job", "resume"}
    assert "不可信" in provider.copilot_calls[0][1]
    assert "RETURN JSON ONLY" in provider.copilot_calls[0][1]
    assert "ALLOWED_SOURCE_IDS" in provider.copilot_calls[0][1]


def test_source_change_marks_old_result_stale_and_failed_regeneration_preserves_it(
    copilot_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, _database_path = copilot_context
    job, resume = _create_sources(client)
    endpoint = f"/api/v1/jobs/{job['id']}/copilot/match"
    request = {"resumeVersionId": resume["id"], "confirmExternalAi": True}
    original = client.post(endpoint, json=request).json()

    client.patch(
        f"/api/v1/resume-versions/{resume['id']}",
        json={"content": "修改后的虚简历正文"},
    )
    stale = client.get(endpoint, params={"resumeVersionId": resume["id"]}).json()
    provider.copilot_error = AnalysisProviderUnavailableError("secret provider detail")
    failed = client.post(endpoint, json=request)
    preserved = client.get(endpoint, params={"resumeVersionId": resume["id"]}).json()

    assert stale["record"]["id"] == original["record"]["id"]
    assert stale["record"]["isStale"] is True
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "AI_PROVIDER_UNAVAILABLE"
    assert "secret" not in failed.text
    assert preserved == stale


def test_invalid_first_response_gets_one_structure_only_repair(
    copilot_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, _database_path = copilot_context
    job, resume = _create_sources(client)
    invalid = '{"summary":"结构不完整"}'
    provider.copilot_responses = [invalid]

    response = client.post(
        f"/api/v1/jobs/{job['id']}/copilot/match",
        json={"resumeVersionId": resume["id"], "confirmExternalAi": True},
    )

    assert response.status_code == 200, response.text
    assert len(provider.copilot_calls) == 2
    assert provider.copilot_calls[0][2] is None
    repair = provider.copilot_calls[1][2]
    assert repair is not None
    assert repair.previous_response == invalid
    assert repair.validator_error == "SCHEMA_MISMATCH"
    assert response.json()["record"]["promptVersion"] == "match-v2"


def test_two_invalid_responses_stop_after_one_retry_and_preserve_previous_record(
    copilot_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, _database_path = copilot_context
    job, resume = _create_sources(client)
    endpoint = f"/api/v1/jobs/{job['id']}/copilot/match"
    request = {"resumeVersionId": resume["id"], "confirmExternalAi": True}
    original = client.post(endpoint, json=request).json()
    provider.copilot_calls.clear()
    provider.copilot_responses = [
        '{"summary":"第一次仍不完整"}',
        '{"summary":"第二次仍不完整"}',
    ]

    failed = client.post(endpoint, json=request)
    preserved = client.get(endpoint, params={"resumeVersionId": resume["id"]})

    assert failed.status_code == 502
    assert failed.json()["error"]["code"] == "AI_INVALID_RESPONSE"
    assert len(provider.copilot_calls) == 2
    assert preserved.json()["record"]["id"] == original["record"]["id"]


def test_provider_transport_failure_is_not_retried(
    copilot_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, _database_path = copilot_context
    job, resume = _create_sources(client)
    provider.copilot_error = AnalysisProviderUnavailableError("secret provider detail")

    response = client.post(
        f"/api/v1/jobs/{job['id']}/copilot/match",
        json={"resumeVersionId": resume["id"], "confirmExternalAi": True},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_PROVIDER_UNAVAILABLE"
    assert len(provider.copilot_calls) == 1


def test_timeout_retries_once_then_succeeds_without_repair(
    copilot_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, _database_path = copilot_context
    job, resume = _create_sources(client)
    provider.copilot_failures = [AnalysisTimeoutError("private first timeout"), None]

    response = client.post(
        f"/api/v1/jobs/{job['id']}/copilot/match",
        json={"resumeVersionId": resume["id"], "confirmExternalAi": True},
    )

    assert response.status_code == 200
    assert len(provider.copilot_calls) == 2
    assert all(call[2] is None for call in provider.copilot_calls)
    assert (
        provider.copilot_calls[0][0].as_provider_data()
        == provider.copilot_calls[1][0].as_provider_data()
    )
    retry_payload = json.dumps(provider.copilot_calls[1][0].as_provider_data(), ensure_ascii=False)
    assert "fictional@example.com" not in retry_payload
    assert "138-0013-8000" not in retry_payload
    assert "private first timeout" not in response.text


def test_two_timeouts_stop_after_second_and_preserve_previous_record(
    copilot_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, _database_path = copilot_context
    job, resume = _create_sources(client)
    endpoint = f"/api/v1/jobs/{job['id']}/copilot/match"
    request = {"resumeVersionId": resume["id"], "confirmExternalAi": True}
    original = client.post(endpoint, json=request).json()
    provider.copilot_calls.clear()
    provider.copilot_failures = [
        AnalysisTimeoutError("private first timeout"),
        AnalysisTimeoutError("private second timeout"),
    ]

    failed = client.post(endpoint, json=request)
    preserved = client.get(endpoint, params={"resumeVersionId": resume["id"]})

    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "AI_TIMEOUT"
    assert "private" not in failed.text
    assert len(provider.copilot_calls) == 2
    assert all(call[2] is None for call in provider.copilot_calls)
    assert preserved.json()["record"]["id"] == original["record"]["id"]


def test_success_uses_one_call_without_timeout_retry(
    copilot_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, _database_path = copilot_context
    job, resume = _create_sources(client)

    response = client.post(
        f"/api/v1/jobs/{job['id']}/copilot/match",
        json={"resumeVersionId": resume["id"], "confirmExternalAi": True},
    )

    assert response.status_code == 200
    assert len(provider.copilot_calls) == 1


def test_invalid_response_does_not_trigger_timeout_retry(
    copilot_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, _database_path = copilot_context
    job, resume = _create_sources(client)
    provider.copilot_responses = ['{"summary":"结构不完整"}']

    response = client.post(
        f"/api/v1/jobs/{job['id']}/copilot/match",
        json={"resumeVersionId": resume["id"], "confirmExternalAi": True},
    )

    assert response.status_code == 200
    assert len(provider.copilot_calls) == 2
    assert provider.copilot_calls[1][2] is not None


def test_invalid_response_after_timeout_retry_cannot_make_third_call(
    copilot_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, _database_path = copilot_context
    job, resume = _create_sources(client)
    provider.copilot_failures = [AnalysisTimeoutError("private timeout"), None]
    provider.copilot_responses = ['{"summary":"结构不完整"}']

    response = client.post(
        f"/api/v1/jobs/{job['id']}/copilot/match",
        json={"resumeVersionId": resume["id"], "confirmExternalAi": True},
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_INVALID_RESPONSE"
    assert len(provider.copilot_calls) == 2
    assert all(call[2] is None for call in provider.copilot_calls)
    assert "private" not in response.text


def test_match_requires_current_analysis_resume_consent_and_provider(
    copilot_context: tuple[TestClient, FakeProvider, Path], tmp_path: Path
) -> None:
    client, _provider, _database_path = copilot_context
    job = _create_job(client)
    resume = _create_resume(client)
    endpoint = f"/api/v1/jobs/{job['id']}/copilot/match"

    assert client.post(endpoint, json={"resumeVersionId": resume["id"]}).status_code == 422
    missing = client.post(
        endpoint,
        json={"resumeVersionId": resume["id"], "confirmExternalAi": True},
    )
    assert missing.json()["error"]["code"] == "JD_ANALYSIS_REQUIRED"

    unconfigured_path = tmp_path / "unconfigured.db"
    _upgrade(unconfigured_path)
    setup = FakeProvider()
    setup_app = create_app(
        ApiSettings.from_environment({}),
        database_path=unconfigured_path,
        analysis_provider=setup,
    )
    with TestClient(setup_app, base_url="http://127.0.0.1") as setup_client:
        configured_job, configured_resume = _create_sources(setup_client)

    app = create_app(ApiSettings.from_environment({}), database_path=unconfigured_path)
    with TestClient(app, base_url="http://127.0.0.1") as unconfigured_client:
        response = unconfigured_client.post(
            f"/api/v1/jobs/{configured_job['id']}/copilot/match",
            json={
                "resumeVersionId": configured_resume["id"],
                "confirmExternalAi": True,
            },
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "AI_NOT_CONFIGURED"


def test_resume_advice_is_grounded_and_persisted(
    copilot_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, _database_path = copilot_context
    job, resume = _create_sources(client)
    endpoint = f"/api/v1/jobs/{job['id']}/copilot/resume-advice"

    response = client.post(
        endpoint,
        json={"resumeVersionId": resume["id"], "confirmExternalAi": True},
    )

    assert response.status_code == 200, response.text
    record = response.json()["record"]
    assert record["kind"] == "RESUME_ADVICE"
    assert record["promptVersion"] == "resume-advice-v2"
    assert record["result"]["highlight"][0]["sourceEvidence"]["sourceType"] == "RESUME"
    assert record["result"]["interviewFocus"][0]["sourceEvidence"]["sourceType"] == "JOB"
    provider_data = json.dumps(provider.copilot_calls[-1][0].as_provider_data())
    assert "fictional@example.com" not in provider_data


def test_interview_prep_uses_rounds_and_becomes_stale_after_review_change(
    copilot_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, _database_path = copilot_context
    job, _resume = _create_sources(client)
    application = client.post(f"/api/v1/jobs/{job['id']}/application", json={}).json()
    interview = client.post(
        f"/api/v1/applications/{application['id']}/interviews",
        json={
            "roundName": "一面",
            "interviewType": "VIDEO",
            "status": "COMPLETED",
            "wentWell": "需求分析思路清楚",
            "couldImprove": "数据指标回答不完整",
        },
    ).json()
    endpoint = f"/api/v1/jobs/{job['id']}/copilot/interview-prep"

    response = client.post(endpoint, json={"confirmExternalAi": True})

    assert response.status_code == 200, response.text
    record = response.json()["record"]
    assert record["resumeVersionId"] is None
    assert record["kind"] == "INTERVIEW_PREP"
    assert record["promptVersion"] == "interview-prep-v2"
    assert {item["category"] for item in record["result"]["possibleQuestions"]} == {
        "PRODUCT",
        "AI",
        "PROJECT",
    }
    assert record["result"]["review"]["strengths"][0]["sourceEvidence"] == {
        "text": "需求分析思路清楚",
        "sourceType": "INTERVIEW",
        "sourceId": interview["id"],
    }
    assert set(provider.copilot_calls[-1][0].as_provider_data()) == {
        "task",
        "job",
        "interviews",
    }

    client.patch(
        f"/api/v1/interviews/{interview['id']}",
        json={"learningNotes": "下次先定义指标口径"},
    )
    stale = client.get(endpoint)
    assert stale.status_code == 200
    assert stale.json()["record"]["isStale"] is True


def _create_sources(client: TestClient) -> tuple[dict[str, object], dict[str, object]]:
    job = _create_job(client)
    analysis = client.post(f"/api/v1/jobs/{job['id']}/analysis", json={})
    assert analysis.status_code == 200, analysis.text
    return job, _create_resume(client)


def _create_job(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/jobs",
        json={
            "title": "AI 产品经理",
            "company": "示例公司",
            "source": "manual",
            "description": "负责 AI 产品需求分析",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_resume(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/resume-versions",
        json={
            "name": "虚构测试简历",
            "content": ("邮箱 fictional@example.com 电话 138-0013-8000\n参与 AI 产品需求分析"),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _upgrade(database_path: Path) -> None:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())
    command.upgrade(config, "head")
