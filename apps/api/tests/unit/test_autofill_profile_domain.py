from __future__ import annotations

import pytest

from jobpilot_api.domain.autofill_profiles import AutofillProfileDraft
from jobpilot_api.domain.errors import DomainValidationError


def test_profile_draft_normalizes_minimal_structured_facts() -> None:
    draft = AutofillProfileDraft.create(
        personal={
            "name": " 示例用户\x00 ",
            "phone": " 000-0000-0000 ",
            "email": " candidate@example.invalid ",
            "current_city": " 示例市 ",
        },
        education=[
            {
                "school": " 示例大学 ",
                "major": " 信息管理 ",
                "degree": " 本科 ",
                "start": "2022-09",
                "end": "2026-06",
            },
            {"school": "示例学院", "major": None, "degree": None, "start": None, "end": None},
        ],
        experience=[
            {
                "company": " 示例公司 ",
                "position": " 产品实习生 ",
                "start": "2025-01",
                "end": "2025-06",
                "description": " 梳理需求\r\n跟进验收。 ",
            }
        ],
        projects=[
            {
                "name": " 示例项目 ",
                "role": " 产品负责人 ",
                "start": "2025-06",
                "end": "2025-08",
                "description": " 需求分析\r\n阶段验收。 ",
            }
        ],
        links={
            "github": " https://github.com/example-candidate ",
            "portfolio": None,
            "homepage": "https://example.invalid",
        },
    )

    assert draft.personal.name == "示例用户"
    assert draft.personal.current_city == "示例市"
    assert [item.school for item in draft.education] == ["示例大学", "示例学院"]
    assert draft.experience[0].description == "梳理需求\n跟进验收。"
    assert draft.projects[0].name == "示例项目"
    assert draft.projects[0].description == "需求分析\n阶段验收。"
    assert draft.links.github == "https://github.com/example-candidate"


@pytest.mark.parametrize("month", ["2026", "2026-13", "26-01", "2026/01"])
def test_profile_draft_rejects_invalid_months(month: str) -> None:
    with pytest.raises(DomainValidationError, match="YYYY-MM"):
        AutofillProfileDraft.create(
            personal={"name": "示例用户"},
            education=[{"school": "示例大学", "start": month}],
            experience=[],
            links={},
        )


def test_profile_draft_rejects_unsafe_links() -> None:
    with pytest.raises(DomainValidationError, match="HTTP"):
        AutofillProfileDraft.create(
            personal={"name": "示例用户"},
            education=[],
            experience=[],
            links={"homepage": "javascript:alert(1)"},
        )


def test_profile_draft_rejects_empty_and_unbounded_collections() -> None:
    with pytest.raises(DomainValidationError, match="at least one"):
        AutofillProfileDraft.create(personal={}, education=[], experience=[], links={})

    with pytest.raises(DomainValidationError, match="education"):
        AutofillProfileDraft.create(
            personal={"name": "示例用户"},
            education=[{"school": f"示例学校 {index}"} for index in range(21)],
            experience=[],
            links={},
        )

    with pytest.raises(DomainValidationError, match="projects"):
        AutofillProfileDraft.create(
            personal={"name": "示例用户"},
            education=[],
            experience=[],
            projects=[{"name": f"示例项目 {index}"} for index in range(21)],
            links={},
        )
