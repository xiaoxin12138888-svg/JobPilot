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


def test_feedback_summary_has_an_unambiguous_empty_state_and_no_zero_percentages(
    client: TestClient,
) -> None:
    _create_job(client, "岗位一", "manual")

    response = client.get("/api/v1/feedback-summary")

    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["hasData"] is False
    assert summary["totals"] == {
        "savedJobs": 1,
        "applications": 0,
        "interviewApplications": 0,
        "interviews": 0,
        "questions": 0,
        "offers": 0,
        "rejected": 0,
    }
    assert [stage["conversionRate"] for stage in summary["funnel"]] == [
        None,
        0.0,
        None,
        None,
    ]


def test_feedback_summary_counts_local_facts_with_frozen_denominators(client: TestClient) -> None:
    resume_v1 = _create_resume(client, "产品版 V1")
    resume_v2 = _create_resume(client, "产品版 V2")

    manual_interviewed = _create_application(client, "手动岗位一", "manual", resume_v1["id"])
    boss_offer = _create_application(client, "BOSS 岗位", "boss", resume_v1["id"])
    nowcoder_rejected = _create_application(client, "牛客岗位", "nowcoder", resume_v2["id"])
    manual_rejected = _create_application(client, "手动岗位二", "manual", None)
    _create_job(client, "只保存岗位", "manual")

    first_round = _create_round(client, manual_interviewed["id"], "一面")
    _create_round(client, manual_interviewed["id"], "二面")
    boss_round = _create_round(client, boss_offer["id"], "业务面")
    manual_round = _create_round(client, manual_rejected["id"], "电话面")

    _create_question(client, first_round["id"], "产品问题一", "PRODUCT", "OK")
    _create_question(client, first_round["id"], "产品问题二", "PRODUCT", "GOOD")
    _create_question(client, boss_round["id"], "AI 问题", "AI", "OK")
    _create_question(client, manual_round["id"], "项目问题", "PROJECT", "POOR")

    _move_to_interviewing(client, boss_offer["id"])
    client.patch(f"/api/v1/applications/{boss_offer['id']}", json={"status": "offer"})
    _move_to_interviewing(client, nowcoder_rejected["id"])
    client.patch(
        f"/api/v1/applications/{nowcoder_rejected['id']}",
        json={"status": "rejected", "rejectionReason": "TECHNICAL"},
    )
    _move_to_interviewing(client, manual_rejected["id"])
    client.patch(f"/api/v1/applications/{manual_rejected['id']}", json={"status": "rejected"})

    summary = client.get("/api/v1/feedback-summary").json()

    assert summary["hasData"] is True
    assert summary["totals"] == {
        "savedJobs": 5,
        "applications": 4,
        "interviewApplications": 3,
        "interviews": 4,
        "questions": 4,
        "offers": 1,
        "rejected": 2,
    }
    assert summary["funnel"] == [
        {"stage": "SAVED_JOBS", "count": 5, "conversionRate": None},
        {"stage": "APPLICATIONS", "count": 4, "conversionRate": 0.8},
        {"stage": "INTERVIEW_APPLICATIONS", "count": 3, "conversionRate": 0.75},
        {"stage": "OFFERS", "count": 1, "conversionRate": 1 / 3},
    ]

    categories = {item["category"]: item["count"] for item in summary["questionCategories"]}
    performances = {item["performance"]: item["count"] for item in summary["performances"]}
    assert categories == {
        "PRODUCT": 2,
        "AI": 1,
        "TECHNICAL": 0,
        "PROJECT": 1,
        "BEHAVIORAL": 0,
        "BUSINESS": 0,
        "OTHER": 0,
    }
    assert performances == {"GOOD": 1, "OK": 2, "POOR": 1, "NOT_SURE": 0}
    assert summary["weakCategories"] == [
        {"category": "PRODUCT", "questionCount": 2, "weakCount": 1},
        {"category": "AI", "questionCount": 1, "weakCount": 1},
        {"category": "PROJECT", "questionCount": 1, "weakCount": 1},
    ]

    reasons = {item["reason"]: item["count"] for item in summary["rejectionReasons"]}
    assert reasons["TECHNICAL"] == 1
    assert summary["unrecordedRejectionReasons"] == 1

    sources = {item["source"]: item for item in summary["sources"]}
    assert sources["manual"] == {
        "source": "manual",
        "applications": 2,
        "interviewApplications": 2,
        "offers": 0,
    }
    assert sources["boss"] == {
        "source": "boss",
        "applications": 1,
        "interviewApplications": 1,
        "offers": 1,
    }
    assert sources["nowcoder"] == {
        "source": "nowcoder",
        "applications": 1,
        "interviewApplications": 0,
        "offers": 0,
    }

    resumes = {item["resumeVersionName"]: item for item in summary["resumeVersions"]}
    assert resumes["产品版 V1"] == {
        "resumeVersionId": resume_v1["id"],
        "resumeVersionName": "产品版 V1",
        "applications": 2,
        "interviewApplications": 2,
        "offers": 1,
    }
    assert resumes["产品版 V2"] == {
        "resumeVersionId": resume_v2["id"],
        "resumeVersionName": "产品版 V2",
        "applications": 1,
        "interviewApplications": 0,
        "offers": 0,
    }


def test_feedback_summary_handles_applications_without_interviews(client: TestClient) -> None:
    _create_application(client, "仅投递岗位", "manual", None)

    summary = client.get("/api/v1/feedback-summary").json()

    assert summary["hasData"] is True
    assert summary["totals"]["applications"] == 1
    assert summary["totals"]["interviewApplications"] == 0
    assert summary["funnel"][1]["conversionRate"] == 1.0
    assert summary["funnel"][2]["conversionRate"] == 0.0
    assert summary["funnel"][3]["conversionRate"] is None


def test_feedback_funnel_omits_rate_when_incomplete_records_would_exceed_100_percent(
    client: TestClient,
) -> None:
    interviewed = _create_application(client, "有面试记录岗位", "manual", None)
    _create_round(client, interviewed["id"], "一面")
    for title in ("漏记面试 Offer 一", "漏记面试 Offer 二"):
        offered = _create_application(client, title, "manual", None)
        _move_to_interviewing(client, offered["id"])
        response = client.patch(
            f"/api/v1/applications/{offered['id']}",
            json={"status": "offer"},
        )
        assert response.status_code == 200, response.text

    summary = client.get("/api/v1/feedback-summary").json()

    assert summary["totals"]["interviewApplications"] == 1
    assert summary["totals"]["offers"] == 2
    assert summary["funnel"][3] == {
        "stage": "OFFERS",
        "count": 2,
        "conversionRate": None,
    }


def test_feedback_summary_works_without_any_provider_configuration(client: TestClient) -> None:
    application = _create_application(client, "无 Provider 岗位", "manual", None)
    _create_round(client, application["id"], "一面")

    response = client.get("/api/v1/feedback-summary")

    assert response.status_code == 200
    assert response.json()["totals"]["interviews"] == 1


def _create_job(client: TestClient, title: str, source: str) -> dict[str, object]:
    source_urls = {
        "boss": "https://www.zhipin.com/job_detail/phase8fixture.html",
        "nowcoder": "https://www.nowcoder.com/jobs/detail/8008",
    }
    response = client.post(
        "/api/v1/jobs",
        json={
            "title": title,
            "company": "虚构公司",
            "source": source,
            "sourceUrl": source_urls.get(source),
            "description": "用于统计测试的虚构岗位。",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_resume(client: TestClient, name: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/resume-versions",
        json={"name": name, "content": f"{name} 的虚构简历正文。"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_application(
    client: TestClient, title: str, source: str, resume_version_id: object | None
) -> dict[str, object]:
    job = _create_job(client, title, source)
    response = client.post(f"/api/v1/jobs/{job['id']}/application", json={})
    assert response.status_code == 201, response.text
    application = response.json()
    if resume_version_id is not None:
        response = client.patch(
            f"/api/v1/applications/{application['id']}",
            json={"resumeVersionId": resume_version_id},
        )
        assert response.status_code == 200, response.text
        application = response.json()
    return application


def _create_round(client: TestClient, application_id: object, round_name: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/applications/{application_id}/interviews",
        json={"roundName": round_name, "interviewType": "VIDEO"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_question(
    client: TestClient,
    interview_id: object,
    question: str,
    category: str,
    performance: str,
) -> None:
    response = client.post(
        f"/api/v1/interviews/{interview_id}/questions",
        json={"question": question, "category": category, "performance": performance},
    )
    assert response.status_code == 201, response.text


def _move_to_interviewing(client: TestClient, application_id: object) -> None:
    applied = client.patch(
        f"/api/v1/applications/{application_id}",
        json={"status": "applied", "confirmApplied": True},
    )
    assert applied.status_code == 200, applied.text
    interviewing = client.patch(
        f"/api/v1/applications/{application_id}", json={"status": "interviewing"}
    )
    assert interviewing.status_code == 200, interviewing.text
