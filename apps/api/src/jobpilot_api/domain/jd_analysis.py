from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from jobpilot_api.domain.errors import AnalysisInvalidResponseError

JD_ANALYSIS_SCHEMA_VERSION = 1
MAX_ANALYSIS_TEXT_LENGTH = 2_000
MAX_ANALYSIS_ITEMS = 100
ANALYSIS_KEYS = frozenset(
    {
        "summary",
        "responsibilities",
        "mustHaveRequirements",
        "preferredRequirements",
        "skills",
        "experienceRequirements",
        "educationRequirements",
        "domainKeywords",
        "interviewFocus",
    }
)
EVIDENCE_KEYS = frozenset({"text", "evidence"})
WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    text: str
    evidence: str | None

    def as_dict(self) -> dict[str, str | None]:
        return {"text": self.text, "evidence": self.evidence}


@dataclass(frozen=True, slots=True)
class JDAnalysis:
    summary: str
    responsibilities: tuple[EvidenceItem, ...]
    must_have_requirements: tuple[EvidenceItem, ...]
    preferred_requirements: tuple[EvidenceItem, ...]
    skills: tuple[str, ...]
    experience_requirements: tuple[EvidenceItem, ...]
    education_requirements: tuple[EvidenceItem, ...]
    domain_keywords: tuple[str, ...]
    interview_focus: tuple[EvidenceItem, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "responsibilities": [item.as_dict() for item in self.responsibilities],
            "mustHaveRequirements": [item.as_dict() for item in self.must_have_requirements],
            "preferredRequirements": [item.as_dict() for item in self.preferred_requirements],
            "skills": list(self.skills),
            "experienceRequirements": [item.as_dict() for item in self.experience_requirements],
            "educationRequirements": [item.as_dict() for item in self.education_requirements],
            "domainKeywords": list(self.domain_keywords),
            "interviewFocus": [item.as_dict() for item in self.interview_focus],
        }


@dataclass(frozen=True, slots=True)
class JDAnalysisInput:
    title: str
    company: str
    description: str
    location: str | None
    salary_text: str | None

    def as_provider_data(self) -> dict[str, str | None]:
        return {
            "title": self.title,
            "company": self.company,
            "description": self.description,
            "location": self.location,
            "salaryText": self.salary_text,
        }

    def fingerprint(self) -> str:
        canonical = json.dumps(
            self.as_provider_data(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True, slots=True)
class JDAnalysisRecord:
    id: str
    job_id: str
    schema_version: int
    result: JDAnalysis
    source_fingerprint: str
    created_at: datetime
    updated_at: datetime


def parse_and_ground_analysis(raw_content: str, description: str) -> JDAnalysis:
    return _parse_analysis(raw_content, _normalize_text(description))


def analysis_from_stored_json(raw_content: str) -> JDAnalysis:
    return _parse_analysis(raw_content, None)


def _parse_analysis(raw_content: str, normalized_description: str | None) -> JDAnalysis:
    try:
        value = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        raise _invalid_response() from None
    if not isinstance(value, dict) or frozenset(value) != ANALYSIS_KEYS:
        raise _invalid_response()

    return JDAnalysis(
        summary=_string(value["summary"], allow_empty=True),
        responsibilities=_evidence_items(value["responsibilities"], normalized_description),
        must_have_requirements=_evidence_items(
            value["mustHaveRequirements"], normalized_description
        ),
        preferred_requirements=_evidence_items(
            value["preferredRequirements"], normalized_description
        ),
        skills=_strings(value["skills"]),
        experience_requirements=_evidence_items(
            value["experienceRequirements"], normalized_description
        ),
        education_requirements=_evidence_items(
            value["educationRequirements"], normalized_description
        ),
        domain_keywords=_strings(value["domainKeywords"]),
        interview_focus=_evidence_items(value["interviewFocus"], normalized_description),
    )


def _evidence_items(value: Any, description: str | None) -> tuple[EvidenceItem, ...]:
    if not isinstance(value, list) or len(value) > MAX_ANALYSIS_ITEMS:
        raise _invalid_response()
    result: list[EvidenceItem] = []
    seen: set[str] = set()
    for raw_item in value:
        if not isinstance(raw_item, dict) or frozenset(raw_item) != EVIDENCE_KEYS:
            raise _invalid_response()
        text = _string(raw_item["text"])
        identity = text.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        raw_evidence = raw_item["evidence"]
        if raw_evidence is not None and not isinstance(raw_evidence, str):
            raise _invalid_response()
        evidence = _normalize_text(raw_evidence) if raw_evidence else None
        if evidence and description is not None and evidence not in description:
            evidence = None
        result.append(EvidenceItem(text=text, evidence=evidence))
    return tuple(result)


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > MAX_ANALYSIS_ITEMS:
        raise _invalid_response()
    result: list[str] = []
    seen: set[str] = set()
    for raw_item in value:
        text = _string(raw_item)
        identity = text.casefold()
        if identity not in seen:
            seen.add(identity)
            result.append(text)
    return tuple(result)


def _string(value: Any, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise _invalid_response()
    normalized = _normalize_text(value)
    if (not normalized and not allow_empty) or len(normalized) > MAX_ANALYSIS_TEXT_LENGTH:
        raise _invalid_response()
    return normalized


def _normalize_text(value: str) -> str:
    return WHITESPACE.sub(" ", value).strip()


def _invalid_response() -> AnalysisInvalidResponseError:
    return AnalysisInvalidResponseError("AI 返回的分析结果无法验证，请稍后重试")
