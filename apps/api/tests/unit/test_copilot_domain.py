from __future__ import annotations

import json

import pytest

from jobpilot_api.domain.copilot import (
    CopilotInput,
    CopilotKind,
    CopilotSource,
    SourceType,
    parse_copilot_result,
)
from jobpilot_api.domain.errors import AnalysisInvalidResponseError

JOB_ID = "00000000-0000-0000-0000-000000000011"
RESUME_ID = "00000000-0000-0000-0000-000000000012"
INTERVIEW_ID = "00000000-0000-0000-0000-000000000013"


def test_provider_input_redacts_contact_details_and_fingerprint_is_deterministic() -> None:
    first = CopilotInput.create(
        kind=CopilotKind.MATCH,
        title="AI 产品经理",
        job_sources=(CopilotSource(JOB_ID, "负责 AI 产品需求分析"),),
        resume_source=CopilotSource(
            RESUME_ID,
            "姓名：小林\n邮箱 lin@example.com\n电话 138-0013-8000\n负责智能问答产品需求分析",
        ),
    )
    second = CopilotInput.create(
        kind=CopilotKind.MATCH,
        title="AI 产品经理",
        job_sources=(CopilotSource(JOB_ID, "负责 AI 产品需求分析"),),
        resume_source=CopilotSource(
            RESUME_ID,
            "姓名：小林\n邮箱 lin@example.com\n电话 138-0013-8000\n负责智能问答产品需求分析",
        ),
    )

    serialized = json.dumps(first.as_provider_data(), ensure_ascii=False)
    assert "lin@example.com" not in serialized
    assert "138-0013-8000" not in serialized
    assert "[联系方式已移除]" in serialized
    assert first.fingerprint() == second.fingerprint()


def test_match_accepts_only_quotes_from_the_declared_source() -> None:
    input_data = _match_input()
    raw = _match_result(resume_quote="虚构的十年 AI 产品经验")

    with pytest.raises(AnalysisInvalidResponseError):
        parse_copilot_result(CopilotKind.MATCH, raw, input_data)


def test_match_rejects_gap_that_claims_user_inability() -> None:
    input_data = _match_input()
    raw = _match_result(gap_text="用户不会 SQL。")

    with pytest.raises(AnalysisInvalidResponseError):
        parse_copilot_result(CopilotKind.MATCH, raw, input_data)


def test_interview_prep_rejects_overclaimed_question_certainty() -> None:
    input_data = CopilotInput.create(
        kind=CopilotKind.INTERVIEW_PREP,
        title="产品经理",
        job_sources=(CopilotSource(JOB_ID, "负责用户研究"),),
        interview_sources=(CopilotSource(INTERVIEW_ID, "复盘：需求拆解回答不够清楚"),),
    )
    raw = json.dumps(
        {
            "possibleQuestions": [
                {
                    "category": "PRODUCT",
                    "question": "面试官一定会问你如何开展用户研究。",
                    "reason": "岗位包含用户研究职责。",
                    "sourceEvidence": {
                        "text": "负责用户研究",
                        "sourceType": "JOB",
                        "sourceId": JOB_ID,
                    },
                }
            ],
            "review": {
                "strengths": [],
                "weaknesses": [],
                "nextActions": ["准备一个需求拆解案例。"],
            },
        },
        ensure_ascii=False,
    )

    with pytest.raises(AnalysisInvalidResponseError):
        parse_copilot_result(CopilotKind.INTERVIEW_PREP, raw, input_data)


def test_valid_match_is_parsed_with_grounded_resume_and_job_evidence() -> None:
    input_data = _match_input()

    result = parse_copilot_result(CopilotKind.MATCH, _match_result(), input_data)

    assert result.as_dict()["strengths"][0]["sourceEvidence"] == {
        "text": "参与 AI 产品需求分析",
        "sourceType": "RESUME",
        "sourceId": RESUME_ID,
    }
    assert result.as_dict()["gaps"][0]["sourceEvidence"]["sourceType"] == "JOB"


def _match_input() -> CopilotInput:
    return CopilotInput.create(
        kind=CopilotKind.MATCH,
        title="AI 产品经理",
        job_sources=(
            CopilotSource(JOB_ID, "负责 AI 产品需求分析"),
            CopilotSource(JOB_ID, "熟练使用 SQL"),
        ),
        resume_source=CopilotSource(RESUME_ID, "参与 AI 产品需求分析，完成需求文档。"),
    )


def _match_result(
    *,
    resume_quote: str = "参与 AI 产品需求分析",
    gap_text: str = "当前简历未发现 SQL 实践证据。",
) -> str:
    return json.dumps(
        {
            "summary": "当前经历与岗位的 AI 产品职责相关，SQL 证据仍需补充。",
            "strengths": [
                {
                    "text": "已有 AI 产品需求分析经历。",
                    "sourceEvidence": {
                        "text": resume_quote,
                        "sourceType": SourceType.RESUME.value,
                        "sourceId": RESUME_ID,
                    },
                }
            ],
            "gaps": [
                {
                    "text": gap_text,
                    "sourceEvidence": {
                        "text": "熟练使用 SQL",
                        "sourceType": SourceType.JOB.value,
                        "sourceId": JOB_ID,
                    },
                }
            ],
            "suggestions": ["准备一个可验证的数据分析案例。"],
        },
        ensure_ascii=False,
    )
