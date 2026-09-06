from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jobpilot_api.domain.applications import (
    ApplicationStatus,
    RejectionReason,
    normalize_application_outcome,
)
from jobpilot_api.domain.errors import DomainValidationError
from jobpilot_api.domain.interviews import (
    InterviewQuestionDraft,
    InterviewRoundDraft,
    InterviewStatus,
    InterviewType,
    QuestionCategory,
    QuestionPerformance,
)


def test_interview_round_draft_normalizes_manual_plain_text() -> None:
    scheduled_at = datetime(2026, 9, 8, 2, 30, tzinfo=UTC)

    draft = InterviewRoundDraft.create(
        round_name="\x00 一面 ",
        interview_type=InterviewType.VIDEO,
        scheduled_at=scheduled_at,
        status=InterviewStatus.COMPLETED,
        interviewer_note=" 产品负责人\r\n技术负责人 ",
        went_well=" 结构化表达 ",
        could_improve=" 案例指标不完整 ",
        learning_notes=" 补充指标设计 ",
        other_notes=" \x1f等待反馈 ",
    )

    assert draft.round_name == "一面"
    assert draft.interviewer_note == "产品负责人\n技术负责人"
    assert draft.went_well == "结构化表达"
    assert draft.could_improve == "案例指标不完整"
    assert draft.learning_notes == "补充指标设计"
    assert draft.other_notes == "等待反馈"
    assert draft.scheduled_at == scheduled_at


def test_interview_round_requires_a_name() -> None:
    with pytest.raises(DomainValidationError, match="roundName"):
        InterviewRoundDraft.create(
            round_name="   ",
            interview_type=InterviewType.PHONE,
            scheduled_at=None,
            status=InterviewStatus.PLANNED,
        )


def test_interview_question_draft_preserves_manual_answer_and_self_assessment() -> None:
    draft = InterviewQuestionDraft.create(
        question=" 为什么选择这个岗位？ ",
        category=QuestionCategory.PRODUCT,
        answer_summary=" 我结合产品经历说明了动机。 ",
        performance=QuestionPerformance.OK,
        note=" 下次补充业务数据。 ",
    )

    assert draft.question == "为什么选择这个岗位？"
    assert draft.category is QuestionCategory.PRODUCT
    assert draft.answer_summary == "我结合产品经历说明了动机。"
    assert draft.performance is QuestionPerformance.OK
    assert draft.note == "下次补充业务数据。"


@pytest.mark.parametrize("category", list(QuestionCategory))
def test_interview_question_accepts_every_frozen_category(category: QuestionCategory) -> None:
    assert (
        InterviewQuestionDraft.create(
            question="虚构面试题",
            category=category,
            answer_summary=None,
            performance=QuestionPerformance.NOT_SURE,
            note=None,
        ).category
        is category
    )


def test_interview_question_rejects_blank_or_oversized_question() -> None:
    with pytest.raises(DomainValidationError, match="question"):
        InterviewQuestionDraft.create(
            question=" ",
            category=QuestionCategory.OTHER,
            answer_summary=None,
            performance=QuestionPerformance.POOR,
            note=None,
        )

    with pytest.raises(DomainValidationError, match="2000"):
        InterviewQuestionDraft.create(
            question="题" * 2001,
            category=QuestionCategory.OTHER,
            answer_summary=None,
            performance=QuestionPerformance.POOR,
            note=None,
        )


def test_application_outcome_allows_optional_manual_note_for_offer() -> None:
    outcome_note, rejection_reason = normalize_application_outcome(
        status=ApplicationStatus.OFFER,
        outcome_note=" 预计十月入职 ",
        rejection_reason=None,
    )

    assert outcome_note == "预计十月入职"
    assert rejection_reason is None


def test_application_outcome_requires_rejected_status_for_a_rejection_reason() -> None:
    with pytest.raises(DomainValidationError, match="rejected"):
        normalize_application_outcome(
            status=ApplicationStatus.INTERVIEWING,
            outcome_note=None,
            rejection_reason=RejectionReason.EXPERIENCE,
        )

    outcome_note, rejection_reason = normalize_application_outcome(
        status=ApplicationStatus.REJECTED,
        outcome_note="二面后未通过",
        rejection_reason=RejectionReason.EXPERIENCE,
    )
    assert outcome_note == "二面后未通过"
    assert rejection_reason is RejectionReason.EXPERIENCE
