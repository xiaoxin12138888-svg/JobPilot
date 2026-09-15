from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from jobpilot_api.domain.errors import (
    AnalysisInvalidResponseDiagnostic,
    AnalysisInvalidResponseError,
)

COPILOT_SCHEMA_VERSION = 2
MAX_COPILOT_ITEMS = 20
MAX_COPILOT_TEXT_LENGTH = 2_000
CONTACT_REPLACEMENT = "[联系方式已移除]"
WHITESPACE = re.compile(r"\s+")
EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])")
PHONE = re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d(?:[-\s]?\d){8}(?!\d)")
INABILITY = re.compile(r"用户(?:不会|没有|不具备|无法)|候选人(?:不会|没有|不具备|无法)")
CERTAINTY = re.compile(r"一定会问|肯定会问|必问|面试官会问")
EXPERIENCE_ADDITION = re.compile(
    r"(?:补充|添加|加入|写入|增加).{0,30}(?:项目|经历|经验|成果|业绩|指标|数据)"
)
TRUTH_CONDITION = re.compile(r"(?:如果|若|如)(?:你|您)?(?:确实|实际|曾经|有|具备)")


class CopilotKind(StrEnum):
    MATCH = "MATCH"
    RESUME_ADVICE = "RESUME_ADVICE"
    INTERVIEW_PREP = "INTERVIEW_PREP"


class SourceType(StrEnum):
    RESUME = "RESUME"
    JOB = "JOB"
    INTERVIEW = "INTERVIEW"


class InterviewQuestionCategory(StrEnum):
    PRODUCT = "PRODUCT"
    AI = "AI"
    PROJECT = "PROJECT"
    TECHNICAL = "TECHNICAL"
    BEHAVIORAL = "BEHAVIORAL"
    DOMAIN = "DOMAIN"


@dataclass(frozen=True, slots=True)
class CopilotSource:
    id: str
    text: str

    def as_provider_data(self) -> dict[str, str]:
        return {"id": self.id, "text": self.text}


@dataclass(frozen=True, slots=True)
class CopilotInput:
    kind: CopilotKind
    title: str
    job_sources: tuple[CopilotSource, ...]
    resume_source: CopilotSource | None
    interview_sources: tuple[CopilotSource, ...]

    @classmethod
    def create(
        cls,
        *,
        kind: CopilotKind,
        title: str,
        job_sources: tuple[CopilotSource, ...],
        resume_source: CopilotSource | None = None,
        interview_sources: tuple[CopilotSource, ...] = (),
    ) -> CopilotInput:
        return cls(
            kind=kind,
            title=redact_contact_details(title),
            job_sources=tuple(_redacted_source(item) for item in job_sources),
            resume_source=_redacted_source(resume_source) if resume_source is not None else None,
            interview_sources=tuple(_redacted_source(item) for item in interview_sources),
        )

    def as_provider_data(self) -> dict[str, object]:
        data: dict[str, object] = {
            "task": self.kind.value,
            "job": {
                "title": self.title,
                "sources": [source.as_provider_data() for source in self.job_sources],
            },
        }
        if self.resume_source is not None:
            data["resume"] = self.resume_source.as_provider_data()
        if self.interview_sources:
            data["interviews"] = [source.as_provider_data() for source in self.interview_sources]
        return data

    def fingerprint(self) -> str:
        canonical = json.dumps(
            self.as_provider_data(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    text: str
    source_type: SourceType
    source_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "text": self.text,
            "sourceType": self.source_type.value,
            "sourceId": self.source_id,
        }


@dataclass(frozen=True, slots=True)
class GroundedCopilotItem:
    text: str
    source_evidence: SourceEvidence

    def as_dict(self) -> dict[str, object]:
        return {"text": self.text, "sourceEvidence": self.source_evidence.as_dict()}


@dataclass(frozen=True, slots=True)
class MatchResult:
    summary: str
    strengths: tuple[GroundedCopilotItem, ...]
    gaps: tuple[GroundedCopilotItem, ...]
    suggestions: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "strengths": [item.as_dict() for item in self.strengths],
            "gaps": [item.as_dict() for item in self.gaps],
            "suggestions": list(self.suggestions),
        }


@dataclass(frozen=True, slots=True)
class ResumeAdviceResult:
    highlight: tuple[GroundedCopilotItem, ...]
    possible_improvement: tuple[str, ...]
    interview_focus: tuple[GroundedCopilotItem, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "highlight": [item.as_dict() for item in self.highlight],
            "possibleImprovement": list(self.possible_improvement),
            "interviewFocus": [item.as_dict() for item in self.interview_focus],
        }


@dataclass(frozen=True, slots=True)
class PossibleInterviewQuestion:
    category: InterviewQuestionCategory
    question: str
    reason: str
    source_evidence: SourceEvidence

    def as_dict(self) -> dict[str, object]:
        return {
            "category": self.category.value,
            "question": self.question,
            "reason": self.reason,
            "sourceEvidence": self.source_evidence.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class InterviewReview:
    strengths: tuple[GroundedCopilotItem, ...]
    weaknesses: tuple[GroundedCopilotItem, ...]
    next_actions: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "strengths": [item.as_dict() for item in self.strengths],
            "weaknesses": [item.as_dict() for item in self.weaknesses],
            "nextActions": list(self.next_actions),
        }


@dataclass(frozen=True, slots=True)
class InterviewPrepResult:
    possible_questions: tuple[PossibleInterviewQuestion, ...]
    review: InterviewReview

    def as_dict(self) -> dict[str, object]:
        return {
            "possibleQuestions": [item.as_dict() for item in self.possible_questions],
            "review": self.review.as_dict(),
        }


type CopilotResult = MatchResult | ResumeAdviceResult | InterviewPrepResult


@dataclass(frozen=True, slots=True)
class CopilotRecord:
    id: str
    job_id: str
    resume_version_id: str | None
    kind: CopilotKind
    schema_version: int
    result: CopilotResult
    input_fingerprint: str
    model: str
    prompt_version: str
    created_at: datetime


def redact_contact_details(value: str) -> str:
    return PHONE.sub(CONTACT_REPLACEMENT, EMAIL.sub(CONTACT_REPLACEMENT, value))


def parse_copilot_result(
    kind: CopilotKind,
    raw_content: str,
    input_data: CopilotInput,
) -> CopilotResult:
    return _parse_result(kind, raw_content, input_data)


def copilot_result_from_stored_json(kind: CopilotKind, raw_content: str) -> CopilotResult:
    return _parse_result(kind, raw_content, None)


def _parse_result(
    kind: CopilotKind,
    raw_content: str,
    input_data: CopilotInput | None,
) -> CopilotResult:
    try:
        value = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        raise _invalid_response(AnalysisInvalidResponseDiagnostic.INVALID_JSON) from None
    if not isinstance(value, dict):
        raise _invalid_response()
    if kind == CopilotKind.MATCH:
        return _match_result(value, input_data)
    if kind == CopilotKind.RESUME_ADVICE:
        return _resume_advice_result(value, input_data)
    return _interview_prep_result(value, input_data)


def _match_result(value: dict[str, Any], input_data: CopilotInput | None) -> MatchResult:
    _require_keys(value, {"summary", "strengths", "gaps", "suggestions"})
    strengths = _grounded_items(value["strengths"], SourceType.RESUME, input_data)
    gaps = _grounded_items(value["gaps"], SourceType.JOB, input_data)
    for gap in gaps:
        if "未发现" not in gap.text or INABILITY.search(gap.text):
            raise _invalid_response()
    return MatchResult(
        summary=_string(value["summary"]),
        strengths=strengths,
        gaps=gaps,
        suggestions=_suggestions(value["suggestions"], input_data),
    )


def _resume_advice_result(
    value: dict[str, Any], input_data: CopilotInput | None
) -> ResumeAdviceResult:
    _require_keys(value, {"highlight", "possibleImprovement", "interviewFocus"})
    return ResumeAdviceResult(
        highlight=_grounded_items(value["highlight"], SourceType.RESUME, input_data),
        possible_improvement=_suggestions(value["possibleImprovement"], input_data),
        interview_focus=_grounded_items(value["interviewFocus"], SourceType.JOB, input_data),
    )


def _interview_prep_result(
    value: dict[str, Any], input_data: CopilotInput | None
) -> InterviewPrepResult:
    _require_keys(value, {"possibleQuestions", "review"})
    questions = _possible_questions(value["possibleQuestions"], input_data)
    if input_data is not None and not questions:
        raise _invalid_response()
    review_value = value["review"]
    if not isinstance(review_value, dict):
        raise _invalid_response()
    _require_keys(review_value, {"strengths", "weaknesses", "nextActions"})
    review = InterviewReview(
        strengths=_grounded_items(review_value["strengths"], SourceType.INTERVIEW, input_data),
        weaknesses=_grounded_items(review_value["weaknesses"], SourceType.INTERVIEW, input_data),
        next_actions=_strings(review_value["nextActions"]),
    )
    return InterviewPrepResult(possible_questions=questions, review=review)


def _possible_questions(
    value: Any, input_data: CopilotInput | None
) -> tuple[PossibleInterviewQuestion, ...]:
    if not isinstance(value, list) or len(value) > MAX_COPILOT_ITEMS:
        raise _invalid_response()
    result: list[PossibleInterviewQuestion] = []
    for raw_item in value:
        if not isinstance(raw_item, dict):
            raise _invalid_response()
        _require_keys(raw_item, {"category", "question", "reason", "sourceEvidence"})
        try:
            category = InterviewQuestionCategory(raw_item["category"])
        except (TypeError, ValueError):
            raise _invalid_response() from None
        question = _string(raw_item["question"])
        if CERTAINTY.search(question):
            raise _invalid_response()
        evidence = _source_evidence(raw_item["sourceEvidence"], SourceType.JOB, input_data)
        result.append(
            PossibleInterviewQuestion(
                category=category,
                question=question,
                reason=_string(raw_item["reason"]),
                source_evidence=evidence,
            )
        )
    return tuple(result)


def _grounded_items(
    value: Any,
    expected_source_type: SourceType,
    input_data: CopilotInput | None,
) -> tuple[GroundedCopilotItem, ...]:
    if not isinstance(value, list) or len(value) > MAX_COPILOT_ITEMS:
        raise _invalid_response()
    result: list[GroundedCopilotItem] = []
    for raw_item in value:
        if not isinstance(raw_item, dict):
            raise _invalid_response()
        _require_keys(raw_item, {"text", "sourceEvidence"})
        result.append(
            GroundedCopilotItem(
                text=_string(raw_item["text"]),
                source_evidence=_source_evidence(
                    raw_item["sourceEvidence"], expected_source_type, input_data
                ),
            )
        )
    return tuple(result)


def _source_evidence(
    value: Any,
    expected_source_type: SourceType,
    input_data: CopilotInput | None,
) -> SourceEvidence:
    if not isinstance(value, dict):
        raise _invalid_response()
    _require_keys(value, {"text", "sourceType", "sourceId"})
    try:
        source_type = SourceType(value["sourceType"])
    except (TypeError, ValueError):
        raise _invalid_response() from None
    if source_type != expected_source_type:
        raise _invalid_response()
    evidence = SourceEvidence(
        text=_string(value["text"]),
        source_type=source_type,
        source_id=_string(value["sourceId"]),
    )
    if input_data is not None and not _is_grounded(evidence, input_data):
        raise _invalid_response()
    return evidence


def _is_grounded(evidence: SourceEvidence, input_data: CopilotInput) -> bool:
    if evidence.source_type == SourceType.JOB:
        sources = input_data.job_sources
    elif evidence.source_type == SourceType.INTERVIEW:
        sources = input_data.interview_sources
    else:
        sources = (input_data.resume_source,) if input_data.resume_source is not None else ()
    normalized_quote = _normalize(evidence.text)
    return bool(normalized_quote) and any(
        source is not None
        and source.id == evidence.source_id
        and normalized_quote in _normalize(source.text)
        for source in sources
    )


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > MAX_COPILOT_ITEMS:
        raise _invalid_response()
    return tuple(_string(item) for item in value)


def _suggestions(value: Any, input_data: CopilotInput | None) -> tuple[str, ...]:
    suggestions = _strings(value)
    if input_data is not None and any(
        EXPERIENCE_ADDITION.search(item) and not TRUTH_CONDITION.search(item)
        for item in suggestions
    ):
        raise _invalid_response()
    return suggestions


def _string(value: Any) -> str:
    if not isinstance(value, str):
        raise _invalid_response()
    result = value.strip()
    if not result or len(result) > MAX_COPILOT_TEXT_LENGTH:
        raise _invalid_response()
    return result


def _require_keys(value: dict[str, Any], keys: set[str]) -> None:
    if set(value) != keys:
        raise _invalid_response()


def _redacted_source(source: CopilotSource) -> CopilotSource:
    return CopilotSource(id=source.id, text=redact_contact_details(source.text))


def _normalize(value: str) -> str:
    return WHITESPACE.sub("", value).casefold()


def _invalid_response(
    diagnostic: AnalysisInvalidResponseDiagnostic = AnalysisInvalidResponseDiagnostic.SCHEMA_MISMATCH,
) -> AnalysisInvalidResponseError:
    return AnalysisInvalidResponseError(
        "AI 返回的 Copilot 结果无法验证，请稍后重试",
        diagnostic_code=diagnostic,
    )
