from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from jobpilot_api.application.providers import EvidenceMapProvider, JDAnalysisProvider
from jobpilot_api.config import ApiSettings
from jobpilot_api.domain.errors import AnalysisProviderUnavailableError
from jobpilot_api.domain.evidence_maps import (
    EvidenceMapInput,
    EvidenceRequirement,
    RequirementType,
    parse_and_ground_evidence_map,
)
from jobpilot_api.domain.jd_analysis import JDAnalysisInput
from jobpilot_api.infrastructure.database.engine import sqlite_database_url
from jobpilot_api.main import create_app

VALID_JD_ANALYSIS = json.dumps(
    {
        "summary": "负责产品与数据工作",
        "responsibilities": [],
        "mustHaveRequirements": [{"text": "熟练使用 SQL", "evidence": "熟练使用 SQL"}],
        "preferredRequirements": [
            {"text": "独立负责产品从0到1上线", "evidence": "独立负责产品从0到1上线"}
        ],
        "skills": [],
        "experienceRequirements": [],
        "educationRequirements": [],
        "domainKeywords": [],
        "interviewFocus": [],
    },
    ensure_ascii=False,
)

VALID_EVIDENCE_MAP = json.dumps(
    {
        "mappings": [
            {
                "requirementType": "MUST_HAVE",
                "requirementText": "熟练使用 SQL",
                "coverage": "DIRECT",
                "resumeEvidence": [{"quote": "使用 SQL 完成业务数据统计"}],
                "reason": "简历原文直接说明 SQL 实践。",
            },
            {
                "requirementType": "PREFERRED",
                "requirementText": "独立负责产品从0到1上线",
                "coverage": "PARTIAL",
                "resumeEvidence": [{"quote": "参与需求评审和版本验收"}],
                "reason": "有上线环节经验，但未证明独立负责完整流程。",
            },
        ]
    },
    ensure_ascii=False,
)

COMPREHENSIVE_JD_ANALYSIS = json.dumps(
    {
        "summary": "负责产品与数据工作",
        "responsibilities": [{"text": "负责市场调研", "evidence": "负责市场调研"}],
        "mustHaveRequirements": [{"text": "2027届", "evidence": "2027届"}],
        "preferredRequirements": [{"text": "有产品实习经验", "evidence": None}],
        "skills": ["SQL"],
        "experienceRequirements": [{"text": "有数据分析项目经验", "evidence": None}],
        "educationRequirements": [{"text": "本科及以上", "evidence": "本科及以上"}],
        "domainKeywords": ["人工智能"],
        "interviewFocus": [{"text": "准备竞品分析案例", "evidence": None}],
    },
    ensure_ascii=False,
)

COMPREHENSIVE_EVIDENCE_MAP = json.dumps(
    {
        "mappings": [
            {
                "requirementType": requirement_type,
                "requirementText": requirement_text,
                "coverage": "GAP",
                "resumeEvidence": [],
                "reason": "结论：当前无法证明；当前简历版本未发现可追溯证据。",
            }
            for requirement_type, requirement_text in [
                ("MUST_HAVE", "2027届"),
                ("PREFERRED", "有产品实习经验"),
                ("RESPONSIBILITY", "负责市场调研"),
                ("SKILL", "SQL"),
                ("EXPERIENCE", "有数据分析项目经验"),
                ("EDUCATION", "本科及以上"),
            ]
        ]
    },
    ensure_ascii=False,
)


class FakeProvider(JDAnalysisProvider, EvidenceMapProvider):
    def __init__(self) -> None:
        self.jd_response = VALID_JD_ANALYSIS
        self.evidence_response = VALID_EVIDENCE_MAP
        self.evidence_error: Exception | None = None
        self.evidence_calls: list[tuple[EvidenceMapInput, str]] = []

    def analyze(self, analysis_input: JDAnalysisInput, *, system_instruction: str) -> str:
        return self.jd_response

    def map_evidence(self, evidence_input: EvidenceMapInput, *, system_instruction: str) -> str:
        self.evidence_calls.append((evidence_input, system_instruction))
        if self.evidence_error is not None:
            raise self.evidence_error
        return self.evidence_response


@pytest.fixture
def evidence_context(tmp_path: Path) -> Iterator[tuple[TestClient, FakeProvider, Path]]:
    database_path = tmp_path / "jobpilot.db"
    _upgrade(database_path)
    provider = FakeProvider()
    application = create_app(
        ApiSettings.from_environment({}),
        database_path=database_path,
        analysis_provider=provider,
        evidence_map_provider=provider,
    )
    with TestClient(application, base_url="http://127.0.0.1") as client:
        yield client, provider, database_path


def test_generate_get_and_minimal_provider_input(
    evidence_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, _database_path = evidence_context
    job = _create_analyzed_job(client)
    resume = _create_resume(client)

    before = client.get(
        f"/api/v1/jobs/{job['id']}/evidence-map",
        params={"resumeVersionId": resume["id"]},
    )
    created = client.post(
        f"/api/v1/jobs/{job['id']}/evidence-map",
        json={"resumeVersionId": resume["id"], "confirmExternalAi": True},
    )
    loaded = client.get(
        f"/api/v1/jobs/{job['id']}/evidence-map",
        params={"resumeVersionId": resume["id"]},
    )

    assert before.json() == {"isConfigured": True, "evidenceMap": None}
    assert created.status_code == 200, created.text
    evidence_map = created.json()["evidenceMap"]
    assert evidence_map["schemaVersion"] == 2
    assert evidence_map["resumeVersionId"] == resume["id"]
    assert evidence_map["isStale"] is False
    assert [item["coverage"] for item in evidence_map["result"]["mappings"]] == [
        "DIRECT",
        "PARTIAL",
    ]
    assert loaded.json() == created.json()

    assert len(provider.evidence_calls) == 1
    evidence_input, system_instruction = provider.evidence_calls[0]
    assert evidence_input.as_provider_data() == {
        "job": {"title": "AI 产品经理", "company": "示例公司"},
        "requirements": [
            {"requirementType": "MUST_HAVE", "requirementText": "熟练使用 SQL"},
            {"requirementType": "PREFERRED", "requirementText": "独立负责产品从0到1上线"},
        ],
        "resumeContent": "使用 SQL 完成业务数据统计。\n参与需求评审和版本验收。",
    }
    assert "不可信" in system_instruction
    assert "quote" in system_instruction
    assert "不是关键词或字面相等" in system_instruction
    assert "组合多段" in system_instruction
    assert "完整 resumeContent" in system_instruction
    assert "1 至 3 条" in system_instruction
    assert "未明确提供毕业年份、预计毕业时间或培养年限" in system_instruction
    assert "通常学制" not in system_instruction
    assert "description" not in evidence_input.as_provider_data()["job"]


def test_generate_includes_all_six_groups_and_upgrades_existing_v1_record(
    evidence_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, database_path = evidence_context
    provider.jd_response = COMPREHENSIVE_JD_ANALYSIS
    provider.evidence_response = COMPREHENSIVE_EVIDENCE_MAP
    job = _create_analyzed_job(client)
    resume = _create_resume(client)
    endpoint = f"/api/v1/jobs/{job['id']}/evidence-map"

    legacy_result = json.dumps(
        {
            "mappings": [
                {
                    "requirementType": "MUST_HAVE",
                    "requirementText": "2027届",
                    "coverage": "GAP",
                    "resumeEvidence": [],
                    "reason": "当前简历版本未发现证据。",
                },
                {
                    "requirementType": "PREFERRED",
                    "requirementText": "有产品实习经验",
                    "coverage": "GAP",
                    "resumeEvidence": [],
                    "reason": "当前简历版本未发现证据。",
                },
            ]
        },
        ensure_ascii=False,
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO evidence_map_records (
                id, job_id, resume_version_id, schema_version, result_json,
                job_analysis_fingerprint, resume_content_fingerprint, created_at, updated_at
            ) VALUES (?, ?, ?, 1, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("legacy-map", job["id"], resume["id"], legacy_result, "a" * 64, "b" * 64),
        )
        connection.commit()

    legacy = client.get(endpoint, params={"resumeVersionId": resume["id"]})
    assert legacy.status_code == 200
    assert legacy.json()["evidenceMap"]["schemaVersion"] == 1
    assert legacy.json()["evidenceMap"]["isStale"] is True

    regenerated = client.post(
        endpoint,
        json={"resumeVersionId": resume["id"], "confirmExternalAi": True},
    )

    assert regenerated.status_code == 200, regenerated.text
    evidence_map = regenerated.json()["evidenceMap"]
    assert evidence_map["id"] == "legacy-map"
    assert evidence_map["schemaVersion"] == 2
    assert [mapping["requirementType"] for mapping in evidence_map["result"]["mappings"]] == [
        "MUST_HAVE",
        "PREFERRED",
        "RESPONSIBILITY",
        "SKILL",
        "EXPERIENCE",
        "EDUCATION",
    ]
    evidence_input, system_instruction = provider.evidence_calls[-1]
    assert [
        item["requirementType"] for item in evidence_input.as_provider_data()["requirements"]
    ] == [
        "MUST_HAVE",
        "PREFERRED",
        "RESPONSIBILITY",
        "SKILL",
        "EXPERIENCE",
        "EDUCATION",
    ]
    assert "每项先明确给出结论" in system_instruction


def test_generation_requires_current_analysis_resume_provider_and_explicit_consent(
    evidence_context: tuple[TestClient, FakeProvider, Path],
    tmp_path: Path,
) -> None:
    client, provider, _database_path = evidence_context
    job = _create_job(client)
    resume = _create_resume(client)
    endpoint = f"/api/v1/jobs/{job['id']}/evidence-map"

    missing_analysis = client.post(
        endpoint,
        json={"resumeVersionId": resume["id"], "confirmExternalAi": True},
    )
    assert missing_analysis.status_code == 422
    assert missing_analysis.json()["error"]["code"] == "JD_ANALYSIS_REQUIRED"

    client.post(f"/api/v1/jobs/{job['id']}/analysis", json={})
    client.patch(f"/api/v1/jobs/{job['id']}", json={"description": "岗位描述已变化"})
    stale_analysis = client.post(
        endpoint,
        json={"resumeVersionId": resume["id"], "confirmExternalAi": True},
    )
    assert stale_analysis.status_code == 422
    assert stale_analysis.json()["error"]["code"] == "JD_ANALYSIS_STALE"
    assert provider.evidence_calls == []

    assert (
        client.post(
            endpoint,
            json={"resumeVersionId": "missing-resume", "confirmExternalAi": True},
        ).status_code
        == 404
    )
    assert (
        client.post(
            endpoint,
            json={"resumeVersionId": resume["id"], "confirmExternalAi": False},
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/jobs/missing/evidence-map", params={"resumeVersionId": resume["id"]}
        ).status_code
        == 404
    )

    unconfigured_path = tmp_path / "unconfigured.db"
    _upgrade(unconfigured_path)
    setup_provider = FakeProvider()
    configured_app = create_app(
        ApiSettings.from_environment({}),
        database_path=unconfigured_path,
        analysis_provider=setup_provider,
        evidence_map_provider=setup_provider,
    )
    with TestClient(configured_app, base_url="http://127.0.0.1") as setup_client:
        other_job = _create_analyzed_job(setup_client)
        other_resume = _create_resume(setup_client)

    unconfigured_app = create_app(ApiSettings.from_environment({}), database_path=unconfigured_path)
    with TestClient(unconfigured_app, base_url="http://127.0.0.1") as other_client:
        unavailable = other_client.post(
            f"/api/v1/jobs/{other_job['id']}/evidence-map",
            json={"resumeVersionId": other_resume["id"], "confirmExternalAi": True},
        )
        assert unavailable.status_code == 503
        assert unavailable.json()["error"]["code"] == "AI_NOT_CONFIGURED"


def test_stale_and_failed_regeneration_preserve_the_last_valid_result(
    evidence_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, provider, _database_path = evidence_context
    job = _create_analyzed_job(client)
    resume = _create_resume(client)
    endpoint = f"/api/v1/jobs/{job['id']}/evidence-map"
    request = {"resumeVersionId": resume["id"], "confirmExternalAi": True}
    original = client.post(endpoint, json=request).json()["evidenceMap"]

    client.patch(f"/api/v1/resume-versions/{resume['id']}", json={"name": "重命名版本"})
    renamed = client.get(endpoint, params={"resumeVersionId": resume["id"]}).json()
    assert renamed["evidenceMap"]["isStale"] is False

    client.patch(
        f"/api/v1/resume-versions/{resume['id']}",
        json={"content": "新的虚构简历正文"},
    )
    stale = client.get(endpoint, params={"resumeVersionId": resume["id"]}).json()
    assert stale["evidenceMap"]["id"] == original["id"]
    assert stale["evidenceMap"]["isStale"] is True

    provider.evidence_error = AnalysisProviderUnavailableError("不得暴露的 provider 详情")
    failed = client.post(endpoint, json=request)
    preserved = client.get(endpoint, params={"resumeVersionId": resume["id"]}).json()
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "AI_PROVIDER_UNAVAILABLE"
    assert "provider" not in failed.text
    assert preserved["evidenceMap"]["id"] == original["id"]
    assert preserved["evidenceMap"]["isStale"] is True


def test_invalid_result_never_overwrites_and_grounding_downgrades_invalid_evidence(
    evidence_context: tuple[TestClient, FakeProvider, Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, provider, _database_path = evidence_context
    job = _create_analyzed_job(client)
    resume = _create_resume(client)
    endpoint = f"/api/v1/jobs/{job['id']}/evidence-map"
    request = {"resumeVersionId": resume["id"], "confirmExternalAi": True}
    original = client.post(endpoint, json=request).json()

    provider.evidence_response = json.dumps(
        {
            "mappings": [
                {
                    "requirementType": "MUST_HAVE",
                    "requirementText": "熟练使用 SQL",
                    "coverage": "DIRECT",
                    "resumeEvidence": [{"quote": "虚构十年 SQL 经验"}],
                    "reason": "虚构内容",
                },
                {
                    "requirementType": "PREFERRED",
                    "requirementText": "独立负责产品从0到1上线",
                    "coverage": "GAP",
                    "resumeEvidence": [],
                    "reason": "当前简历没有完整证据。",
                },
            ]
        },
        ensure_ascii=False,
    )
    grounded = client.post(endpoint, json=request)
    first_mapping = grounded.json()["evidenceMap"]["result"]["mappings"][0]
    assert first_mapping["coverage"] == "GAP"
    assert first_mapping["resumeEvidence"] == []

    provider.evidence_response = '{"mappings":[],"fitScore":99}'
    with caplog.at_level(logging.WARNING, logger="jobpilot_api.evidence_map_diagnostics"):
        invalid = client.post(endpoint, json=request)
    preserved = client.get(endpoint, params={"resumeVersionId": resume["id"]})
    assert invalid.status_code == 502
    assert invalid.json()["error"]["code"] == "AI_INVALID_RESPONSE"
    assert "fitScore" not in invalid.text
    assert "diagnostic=SCHEMA_MISMATCH" in caplog.text
    assert "fitScore" not in caplog.text
    assert "使用 SQL 完成业务数据统计" not in caplog.text
    assert preserved.json() == grounded.json()
    assert preserved.json() != original


def test_grounding_keeps_partial_cohort_without_external_inference() -> None:
    requirements = (EvidenceRequirement(RequirementType.MUST_HAVE, "2027届"),)
    raw_content = json.dumps(
        {
            "mappings": [
                {
                    "requirementType": "MUST_HAVE",
                    "requirementText": "2027届",
                    "coverage": "PARTIAL",
                    "resumeEvidence": [
                        {"quote": "2025.09—至今"},
                        {"quote": "硕士在读"},
                    ],
                    "reason": "当前简历显示硕士在读，但未明确提供预计毕业年份，因此只能部分支持，需用户确认。",
                }
            ]
        },
        ensure_ascii=False,
    )

    result = parse_and_ground_evidence_map(
        raw_content,
        requirements,
        "教育经历\n2025.09—至今\n硕士在读",
    )

    assert result.as_dict() == {
        "mappings": [
            {
                "requirementType": "MUST_HAVE",
                "requirementText": "2027届",
                "coverage": "PARTIAL",
                "resumeEvidence": [
                    {"quote": "2025.09—至今"},
                    {"quote": "硕士在读"},
                ],
                "reason": "当前简历显示硕士在读，但未明确提供预计毕业年份，因此只能部分支持，需用户确认。",
            }
        ]
    }
    assert "通常" not in result.mappings[0].reason


def test_jd_reanalysis_marks_map_stale_and_deletions_cascade(
    evidence_context: tuple[TestClient, FakeProvider, Path],
) -> None:
    client, _provider, database_path = evidence_context
    job = _create_analyzed_job(client)
    resume = _create_resume(client)
    endpoint = f"/api/v1/jobs/{job['id']}/evidence-map"
    client.post(
        endpoint,
        json={"resumeVersionId": resume["id"], "confirmExternalAi": True},
    )

    client.post(f"/api/v1/jobs/{job['id']}/analysis", json={})
    stale = client.get(endpoint, params={"resumeVersionId": resume["id"]})
    assert stale.json()["evidenceMap"]["isStale"] is True

    application = client.post(f"/api/v1/jobs/{job['id']}/application", json={}).json()
    assert application["resumeVersionId"] is None
    assert client.delete(f"/api/v1/jobs/{job['id']}").status_code == 204
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT count(*) FROM evidence_map_records").fetchone()[0] == 0


def _upgrade(database_path: Path) -> None:
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())
    command.upgrade(config, "head")


def _create_job(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/jobs",
        json={
            "title": "AI 产品经理",
            "company": "示例公司",
            "description": "要求熟练使用 SQL；独立负责产品从0到1上线。",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_analyzed_job(client: TestClient) -> dict[str, object]:
    job = _create_job(client)
    response = client.post(f"/api/v1/jobs/{job['id']}/analysis", json={})
    assert response.status_code == 200, response.text
    return job


def _create_resume(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/resume-versions",
        json={
            "name": "AI 产品经理版",
            "content": "使用 SQL 完成业务数据统计。\n参与需求评审和版本验收。",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
