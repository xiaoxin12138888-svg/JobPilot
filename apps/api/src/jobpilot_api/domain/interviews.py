from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from jobpilot_api.domain.errors import DomainValidationError
from jobpilot_api.domain.jobs import CONTROL_CHARACTER_TRANSLATION

MAX_ROUND_NAME_LENGTH = 200
MAX_QUESTION_LENGTH = 2_000
MAX_INTERVIEW_TEXT_LENGTH = 20_000


class InterviewType(StrEnum):
    PHONE = "PHONE"
    VIDEO = "VIDEO"
    ONSITE = "ONSITE"
    OTHER = "OTHER"


class InterviewStatus(StrEnum):
    PLANNED = "PLANNED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class QuestionCategory(StrEnum):
    PRODUCT = "PRODUCT"
    AI = "AI"
    TECHNICAL = "TECHNICAL"
    PROJECT = "PROJECT"
    BEHAVIORAL = "BEHAVIORAL"
    BUSINESS = "BUSINESS"
    OTHER = "OTHER"


class QuestionPerformance(StrEnum):
    GOOD = "GOOD"
    OK = "OK"
    POOR = "POOR"
    NOT_SURE = "NOT_SURE"


@dataclass(frozen=True, slots=True)
class InterviewRoundDraft:
    round_name: str
    interview_type: InterviewType
    scheduled_at: datetime | None
    status: InterviewStatus
    interviewer_note: str | None
    went_well: str | None
    could_improve: str | None
    learning_notes: str | None
    other_notes: str | None

    @classmethod
    def create(
        cls,
        *,
        round_name: str,
        interview_type: InterviewType,
        scheduled_at: datetime | None,
        status: InterviewStatus,
        interviewer_note: str | None = None,
        went_well: str | None = None,
        could_improve: str | None = None,
        learning_notes: str | None = None,
        other_notes: str | None = None,
    ) -> InterviewRoundDraft:
        return cls(
            round_name=_required_plain_text("roundName", round_name, MAX_ROUND_NAME_LENGTH),
            interview_type=interview_type,
            scheduled_at=scheduled_at,
            status=status,
            interviewer_note=_optional_plain_text("interviewerNote", interviewer_note),
            went_well=_optional_plain_text("wentWell", went_well),
            could_improve=_optional_plain_text("couldImprove", could_improve),
            learning_notes=_optional_plain_text("learningNotes", learning_notes),
            other_notes=_optional_plain_text("otherNotes", other_notes),
        )


@dataclass(frozen=True, slots=True)
class InterviewRound:
    id: str
    application_id: str
    round_name: str
    interview_type: InterviewType
    scheduled_at: datetime | None
    status: InterviewStatus
    interviewer_note: str | None
    went_well: str | None
    could_improve: str | None
    learning_notes: str | None
    other_notes: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class InterviewQuestionDraft:
    question: str
    category: QuestionCategory
    answer_summary: str | None
    performance: QuestionPerformance
    note: str | None

    @classmethod
    def create(
        cls,
        *,
        question: str,
        category: QuestionCategory,
        answer_summary: str | None,
        performance: QuestionPerformance,
        note: str | None,
    ) -> InterviewQuestionDraft:
        return cls(
            question=_required_plain_text("question", question, MAX_QUESTION_LENGTH),
            category=category,
            answer_summary=_optional_plain_text("answerSummary", answer_summary),
            performance=performance,
            note=_optional_plain_text("note", note),
        )


@dataclass(frozen=True, slots=True)
class InterviewQuestion:
    id: str
    interview_round_id: str
    question: str
    category: QuestionCategory
    answer_summary: str | None
    performance: QuestionPerformance
    note: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class InterviewRoundDetail:
    interview: InterviewRound
    questions: tuple[InterviewQuestion, ...]


def _required_plain_text(field: str, value: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise DomainValidationError(f"{field}: must be text")
    cleaned = _plain_text(value).strip()
    if not cleaned:
        raise DomainValidationError(f"{field}: must not be blank")
    if len(cleaned) > maximum:
        raise DomainValidationError(f"{field}: must be at most {maximum} characters")
    return cleaned


def _optional_plain_text(field: str, value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DomainValidationError(f"{field}: must be text")
    cleaned = _plain_text(value).strip()
    if not cleaned:
        return None
    if len(cleaned) > MAX_INTERVIEW_TEXT_LENGTH:
        raise DomainValidationError(
            f"{field}: must be at most {MAX_INTERVIEW_TEXT_LENGTH} characters"
        )
    return cleaned


def _plain_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").translate(CONTROL_CHARACTER_TRANSLATION)
