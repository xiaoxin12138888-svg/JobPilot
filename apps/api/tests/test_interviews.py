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
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", sqlite_database_url(database_path).render_as_string())
    command.upgrade(config, "head")
    application = create_app(ApiSettings.from_environment({}), database_path=database_path)
    with TestClient(application, base_url="http://127.0.0.1") as active_client:
        yield active_client


def test_interview_round_crud_self_review_and_completion_do_not_change_application(
    client: TestClient,
) -> None:
    application = _create_application(client)

    created = client.post(
        f"/api/v1/applications/{application['id']}/interviews",
        json={
            "roundName": "一面",
            "interviewType": "VIDEO",
            "scheduledAt": "2026-09-08T10:30:00+08:00",
            "status": "PLANNED",
            "interviewerNote": "产品负责人和技术负责人",
        },
    )

    assert created.status_code == 201, created.text
    interview = created.json()
    assert interview["roundName"] == "一面"
    assert interview["interviewType"] == "VIDEO"
    assert interview["status"] == "PLANNED"
    assert interview["questions"] == []
    assert client.get(f"/api/v1/applications/{application['id']}").json()["status"] == "planned"

    updated = client.patch(
        f"/api/v1/interviews/{interview['id']}",
        json={
            "status": "COMPLETED",
            "wentWell": "结构化说明了产品决策。",
            "couldImprove": "案例中的指标不够具体。",
            "learningNotes": "补充留存率与转化率拆解。",
            "otherNotes": "等待后续反馈。",
        },
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "COMPLETED"
    assert updated.json()["wentWell"] == "结构化说明了产品决策。"
    assert updated.json()["couldImprove"] == "案例中的指标不够具体。"
    assert updated.json()["learningNotes"] == "补充留存率与转化率拆解。"
    assert updated.json()["otherNotes"] == "等待后续反馈。"
    assert client.get(f"/api/v1/applications/{application['id']}").json()["status"] == "planned"

    listed = client.get(f"/api/v1/applications/{application['id']}/interviews")
    detail = client.get(f"/api/v1/interviews/{interview['id']}")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0] == detail.json()

    deleted = client.delete(f"/api/v1/interviews/{interview['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/interviews/{interview['id']}").status_code == 404


def test_interview_requires_an_existing_application_and_non_empty_patch(
    client: TestClient,
) -> None:
    missing_parent = client.post(
        "/api/v1/applications/missing/interviews",
        json={"roundName": "一面", "interviewType": "PHONE"},
    )
    application = _create_application(client)
    interview = _create_interview(client, application["id"])
    empty_patch = client.patch(f"/api/v1/interviews/{interview['id']}", json={})

    assert missing_parent.status_code == 404
    assert missing_parent.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert empty_patch.status_code == 422
    assert empty_patch.json()["error"]["code"] == "VALIDATION_ERROR"


def test_interview_question_crud_category_performance_and_round_cascade(
    client: TestClient,
) -> None:
    application = _create_application(client)
    interview = _create_interview(client, application["id"])

    first = _create_question(
        client,
        interview["id"],
        question="为什么选择这个岗位？",
        category="PRODUCT",
        performance="OK",
    )
    second = _create_question(
        client,
        interview["id"],
        question="如何设计一个 AI 功能的评测方案？",
        category="AI",
        performance="POOR",
    )

    updated = client.patch(
        f"/api/v1/interview-questions/{first['id']}",
        json={
            "answerSummary": "我用用户价值、风险和指标三部分回答。",
            "performance": "GOOD",
            "note": "保留这个结构。",
        },
    )
    detail = client.get(f"/api/v1/interviews/{interview['id']}")

    assert updated.status_code == 200, updated.text
    assert updated.json()["performance"] == "GOOD"
    assert updated.json()["answerSummary"] == "我用用户价值、风险和指标三部分回答。"
    assert [question["id"] for question in detail.json()["questions"]] == [
        first["id"],
        second["id"],
    ]

    assert client.delete(f"/api/v1/interview-questions/{second['id']}").status_code == 204
    assert len(client.get(f"/api/v1/interviews/{interview['id']}").json()["questions"]) == 1

    assert client.delete(f"/api/v1/interviews/{interview['id']}").status_code == 204
    missing_question = client.patch(
        f"/api/v1/interview-questions/{first['id']}", json={"performance": "OK"}
    )
    assert missing_question.status_code == 404


def test_question_requires_an_existing_round_and_valid_frozen_enums(client: TestClient) -> None:
    missing = client.post(
        "/api/v1/interviews/missing/questions",
        json={
            "question": "虚构问题",
            "category": "PROJECT",
            "performance": "NOT_SURE",
        },
    )
    application = _create_application(client)
    interview = _create_interview(client, application["id"])
    invalid = client.post(
        f"/api/v1/interviews/{interview['id']}/questions",
        json={"question": "虚构问题", "category": "AUTO", "performance": "SCORE_80"},
    )

    assert missing.status_code == 404
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"


def test_application_outcome_note_and_user_recorded_rejection_reason(client: TestClient) -> None:
    application = _create_application(client)
    application_id = application["id"]
    client.patch(
        f"/api/v1/applications/{application_id}",
        json={"status": "applied", "confirmApplied": True},
    )
    client.patch(f"/api/v1/applications/{application_id}", json={"status": "interviewing"})
    rejected = client.patch(
        f"/api/v1/applications/{application_id}",
        json={
            "status": "rejected",
            "outcomeNote": "二面后未通过",
            "rejectionReason": "EXPERIENCE",
        },
    )

    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["outcomeNote"] == "二面后未通过"
    assert rejected.json()["rejectionReason"] == "EXPERIENCE"

    corrected = client.patch(
        f"/api/v1/applications/{application_id}", json={"status": "interviewing"}
    )
    invalid_reason = client.patch(
        f"/api/v1/applications/{application_id}", json={"rejectionReason": "TECHNICAL"}
    )

    assert corrected.json()["outcomeNote"] == "二面后未通过"
    assert corrected.json()["rejectionReason"] is None
    assert invalid_reason.status_code == 422
    assert invalid_reason.json()["error"]["code"] == "VALIDATION_ERROR"


def test_job_deletion_cascades_application_rounds_and_questions(client: TestClient) -> None:
    job = _create_job(client)
    application = client.post(f"/api/v1/jobs/{job['id']}/application", json={}).json()
    interview = _create_interview(client, application["id"])
    question = _create_question(
        client,
        interview["id"],
        question="请介绍一个虚构项目。",
        category="PROJECT",
        performance="NOT_SURE",
    )

    assert client.delete(f"/api/v1/jobs/{job['id']}").status_code == 204
    assert client.get(f"/api/v1/interviews/{interview['id']}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/interview-questions/{question['id']}", json={"performance": "OK"}
        ).status_code
        == 404
    )


def _create_job(client: TestClient, *, source: str = "manual") -> dict[str, object]:
    response = client.post(
        "/api/v1/jobs",
        json={
            "title": "虚构产品岗位",
            "company": "虚构公司",
            "source": source,
            "description": "用于自动化测试的虚构岗位说明。",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_application(client: TestClient) -> dict[str, object]:
    job = _create_job(client)
    response = client.post(f"/api/v1/jobs/{job['id']}/application", json={})
    assert response.status_code == 201, response.text
    return response.json()


def _create_interview(client: TestClient, application_id: object) -> dict[str, object]:
    response = client.post(
        f"/api/v1/applications/{application_id}/interviews",
        json={"roundName": "一面", "interviewType": "VIDEO"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_question(
    client: TestClient,
    interview_id: object,
    *,
    question: str,
    category: str,
    performance: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/interviews/{interview_id}/questions",
        json={
            "question": question,
            "category": category,
            "answerSummary": "虚构回答摘要。",
            "performance": performance,
            "note": "虚构复盘备注。",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
