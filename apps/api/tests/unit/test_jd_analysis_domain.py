from __future__ import annotations

import json

import pytest

from jobpilot_api.domain.errors import AnalysisInvalidResponseError
from jobpilot_api.domain.jd_analysis import (
    JDAnalysisInput,
    parse_and_ground_analysis,
)


def test_valid_structured_analysis_is_normalized_and_grounded() -> None:
    description = "负责 用户需求分析\n并输出产品方案。熟悉 SQL 优先。"
    result = parse_and_ground_analysis(
        json.dumps(
            {
                "summary": "  负责产品需求分析  ",
                "responsibilities": [{"text": "分析用户需求", "evidence": "负责 用户需求分析"}],
                "mustHaveRequirements": [],
                "preferredRequirements": [{"text": "熟悉 SQL", "evidence": "熟悉 SQL 优先"}],
                "skills": [" SQL ", "SQL", "需求分析"],
                "experienceRequirements": [],
                "educationRequirements": [],
                "domainKeywords": [" 产品 ", "产品"],
                "interviewFocus": [{"text": "说明需求分析方法", "evidence": "用户需求分析"}],
            },
            ensure_ascii=False,
        ),
        description,
    )

    assert result.summary == "负责产品需求分析"
    assert result.responsibilities[0].evidence == "负责 用户需求分析"
    assert result.skills == ("SQL", "需求分析")
    assert result.domain_keywords == ("产品",)


def test_unsupported_evidence_is_normalized_to_null() -> None:
    result = parse_and_ground_analysis(
        json.dumps(
            {
                "summary": "",
                "responsibilities": [{"text": "负责团队管理", "evidence": "管理十人团队"}],
                "mustHaveRequirements": [],
                "preferredRequirements": [],
                "skills": [],
                "experienceRequirements": [],
                "educationRequirements": [],
                "domainKeywords": [],
                "interviewFocus": [],
            },
            ensure_ascii=False,
        ),
        "负责产品设计。",
    )

    assert result.responsibilities[0].text == "负责团队管理"
    assert result.responsibilities[0].evidence is None


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        json.dumps([]),
        json.dumps({"summary": "missing fields"}),
        json.dumps(
            {
                "summary": "",
                "responsibilities": [],
                "mustHaveRequirements": [],
                "preferredRequirements": [],
                "skills": "SQL",
                "experienceRequirements": [],
                "educationRequirements": [],
                "domainKeywords": [],
                "interviewFocus": [],
            }
        ),
        json.dumps(
            {
                "summary": "",
                "responsibilities": [],
                "mustHaveRequirements": [],
                "preferredRequirements": [],
                "skills": [],
                "experienceRequirements": [],
                "educationRequirements": [],
                "domainKeywords": [],
                "interviewFocus": [],
                "extra": "not allowed",
            }
        ),
    ],
)
def test_malformed_or_schema_invalid_analysis_is_rejected(payload: str) -> None:
    with pytest.raises(AnalysisInvalidResponseError):
        parse_and_ground_analysis(payload, "岗位描述")


def test_analysis_input_contains_only_approved_fields_and_has_stable_fingerprint() -> None:
    analysis_input = JDAnalysisInput(
        title="产品经理",
        company="示例公司",
        description="负责需求分析",
        location="北京",
        salary_text=None,
    )

    assert analysis_input.as_provider_data() == {
        "title": "产品经理",
        "company": "示例公司",
        "description": "负责需求分析",
        "location": "北京",
        "salaryText": None,
    }
    assert analysis_input.fingerprint() == analysis_input.fingerprint()
    assert (
        analysis_input.fingerprint()
        != JDAnalysisInput(
            title="产品经理",
            company="示例公司",
            description="负责另一项工作",
            location="北京",
            salary_text=None,
        ).fingerprint()
    )
