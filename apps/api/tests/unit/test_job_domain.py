from __future__ import annotations

import pytest

from jobpilot_api.domain.applications import ApplicationStatus, validate_status_transition
from jobpilot_api.domain.errors import DomainValidationError, InvalidTransitionError
from jobpilot_api.domain.jobs import JobDraft, normalize_source_url


def test_job_draft_trims_user_text_and_normalizes_an_http_url() -> None:
    draft = JobDraft.create(
        title="  AI 产品经理实习生 ",
        company=" 测试公司 ",
        location=" 上海 ",
        salary_text=" 200-300/天 ",
        source="manual",
        source_url="HTTPS://Example.COM:443/jobs/1?from=feed#apply",
        description=" 负责 AI 产品设计 ",
        notes=" 优先准备作品集 ",
    )

    assert draft.title == "AI 产品经理实习生"
    assert draft.company == "测试公司"
    assert draft.source_url == "HTTPS://Example.COM:443/jobs/1?from=feed#apply"
    assert draft.normalized_source_url == "https://example.com/jobs/1?from=feed"


def test_job_draft_accepts_a_boss_job_detail_source() -> None:
    draft = JobDraft.create(
        title="产品经理",
        company="测试公司",
        source="boss",
        source_url="https://www.zhipin.com/job_detail/fixture123.html?ka=search_list_jname",
    )

    assert draft.source == "boss"
    assert draft.source_url == "https://www.zhipin.com/job_detail/fixture123.html"
    assert draft.normalized_source_url == "https://www.zhipin.com/job_detail/fixture123.html"


@pytest.mark.parametrize(
    ("source", "source_url"),
    [
        ("other", "https://www.zhipin.com/job_detail/fixture123.html"),
        ("boss", None),
        ("boss", "https://example.com/job_detail/fixture123.html"),
        ("boss", "https://www.zhipin.com/web/geek/job"),
        ("boss", "https://www.zhipin.com:444/job_detail/fixture123.html"),
        ("boss", "https://www.zhipin.com/job_detail/nested/fixture123.html"),
    ],
)
def test_job_draft_rejects_an_unsupported_source_or_boss_page(
    source: str,
    source_url: str | None,
) -> None:
    with pytest.raises(DomainValidationError, match="source"):
        JobDraft.create(
            title="岗位",
            company="公司",
            source=source,
            source_url=source_url,
        )


def test_job_draft_removes_control_characters_and_normalizes_line_endings() -> None:
    draft = JobDraft.create(
        title="\x00 产品\x1f经理 \r",
        company="公\x7f司",
        location="\x1b 上海 ",
        description="第一行\r\n第二\x00行\r第三行",
    )

    assert draft.title == "产品经理"
    assert draft.company == "公司"
    assert draft.location == "上海"
    assert draft.description == "第一行\n第二行\n第三行"


@pytest.mark.parametrize("field", ["title", "company"])
def test_job_draft_rejects_blank_required_text(field: str) -> None:
    values = {"title": "岗位", "company": "公司"}
    values[field] = "   "

    with pytest.raises(DomainValidationError, match=field):
        JobDraft.create(**values)


@pytest.mark.parametrize(
    "url",
    ["ftp://example.com/job", "https://user:secret@example.com/job", "not a url"],
)
def test_job_draft_rejects_unsafe_or_invalid_source_urls(url: str) -> None:
    with pytest.raises(DomainValidationError, match="sourceUrl"):
        JobDraft.create(title="岗位", company="公司", source_url=url)


def test_url_normalization_removes_default_port_and_fragment_but_keeps_query() -> None:
    assert (
        normalize_source_url("http://EXAMPLE.com:80/jobs/1?a=2#details")
        == "http://example.com/jobs/1?a=2"
    )
    assert normalize_source_url(None) is None


def test_transition_into_applied_always_requires_explicit_confirmation() -> None:
    with pytest.raises(DomainValidationError, match="确认"):
        validate_status_transition(
            ApplicationStatus.PLANNED,
            ApplicationStatus.APPLIED,
            confirm_applied=False,
        )

    validate_status_transition(
        ApplicationStatus.PLANNED,
        ApplicationStatus.APPLIED,
        confirm_applied=True,
    )


def test_application_allows_forward_progress_and_adjacent_correction() -> None:
    validate_status_transition(
        ApplicationStatus.APPLIED,
        ApplicationStatus.SCREENING,
        confirm_applied=False,
    )
    validate_status_transition(
        ApplicationStatus.SCREENING,
        ApplicationStatus.APPLIED,
        confirm_applied=True,
    )
    with pytest.raises(DomainValidationError, match="确认"):
        validate_status_transition(
            ApplicationStatus.SCREENING,
            ApplicationStatus.APPLIED,
            confirm_applied=False,
        )
    validate_status_transition(
        ApplicationStatus.INTERVIEWING,
        ApplicationStatus.OFFER,
        confirm_applied=False,
    )


def test_application_rejects_an_invalid_jump() -> None:
    with pytest.raises(InvalidTransitionError):
        validate_status_transition(
            ApplicationStatus.PLANNED,
            ApplicationStatus.OFFER,
            confirm_applied=False,
        )
