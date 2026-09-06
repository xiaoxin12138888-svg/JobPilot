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
from jobpilot_api.domain.jd_analysis import MAX_ANALYSIS_ITEMS, JDAnalysisRecord

EVIDENCE_MAP_SCHEMA_VERSION = 2
MAX_EVIDENCE_MAPPINGS = MAX_ANALYSIS_ITEMS * 6
MAX_GENERATED_RESUME_EVIDENCE_ITEMS = 3
MAX_STORED_RESUME_EVIDENCE_ITEMS = 20
MAX_EVIDENCE_TEXT_LENGTH = 2_000
GROUNDED_GAP_REASON = "当前简历版本中未发现可证明该要求的有效原文证据。"
MAP_KEYS = frozenset({"mappings"})
MAPPING_KEYS = frozenset(
    {"requirementType", "requirementText", "coverage", "resumeEvidence", "reason"}
)
RESUME_EVIDENCE_KEYS = frozenset({"quote"})
WHITESPACE = re.compile(r"\s+")


class RequirementType(StrEnum):
    MUST_HAVE = "MUST_HAVE"
    PREFERRED = "PREFERRED"
    RESPONSIBILITY = "RESPONSIBILITY"
    SKILL = "SKILL"
    EXPERIENCE = "EXPERIENCE"
    EDUCATION = "EDUCATION"


class Coverage(StrEnum):
    DIRECT = "DIRECT"
    PARTIAL = "PARTIAL"
    GAP = "GAP"


@dataclass(frozen=True, slots=True)
class EvidenceRequirement:
    requirement_type: RequirementType
    requirement_text: str

    def as_dict(self) -> dict[str, str]:
        return {
            "requirementType": self.requirement_type.value,
            "requirementText": self.requirement_text,
        }


@dataclass(frozen=True, slots=True)
class ResumeEvidence:
    quote: str

    def as_dict(self) -> dict[str, str]:
        return {"quote": self.quote}


@dataclass(frozen=True, slots=True)
class EvidenceMapping:
    requirement_type: RequirementType
    requirement_text: str
    coverage: Coverage
    resume_evidence: tuple[ResumeEvidence, ...]
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "requirementType": self.requirement_type.value,
            "requirementText": self.requirement_text,
            "coverage": self.coverage.value,
            "resumeEvidence": [item.as_dict() for item in self.resume_evidence],
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class EvidenceMap:
    mappings: tuple[EvidenceMapping, ...]

    def as_dict(self) -> dict[str, object]:
        return {"mappings": [item.as_dict() for item in self.mappings]}


@dataclass(frozen=True, slots=True)
class EvidenceMapInput:
    title: str
    company: str | None
    requirements: tuple[EvidenceRequirement, ...]
    resume_content: str

    def as_provider_data(self) -> dict[str, object]:
        return {
            "job": {"title": self.title, "company": self.company},
            "requirements": [item.as_dict() for item in self.requirements],
            "resumeContent": self.resume_content,
        }

    def fingerprint(self) -> str:
        return _fingerprint(self.as_provider_data())


@dataclass(frozen=True, slots=True)
class EvidenceMapRecord:
    id: str
    job_id: str
    resume_version_id: str
    schema_version: int
    result: EvidenceMap
    job_analysis_fingerprint: str
    resume_content_fingerprint: str
    created_at: datetime
    updated_at: datetime


def requirements_from_analysis(record: JDAnalysisRecord) -> tuple[EvidenceRequirement, ...]:
    result = record.result
    return (
        tuple(
            EvidenceRequirement(RequirementType.MUST_HAVE, item.text)
            for item in result.must_have_requirements
        )
        + tuple(
            EvidenceRequirement(RequirementType.PREFERRED, item.text)
            for item in result.preferred_requirements
        )
        + tuple(
            EvidenceRequirement(RequirementType.RESPONSIBILITY, item.text)
            for item in result.responsibilities
        )
        + tuple(EvidenceRequirement(RequirementType.SKILL, item) for item in result.skills)
        + tuple(
            EvidenceRequirement(RequirementType.EXPERIENCE, item.text)
            for item in result.experience_requirements
        )
        + tuple(
            EvidenceRequirement(RequirementType.EDUCATION, item.text)
            for item in result.education_requirements
        )
    )


def job_analysis_fingerprint(record: JDAnalysisRecord) -> str:
    return _fingerprint(
        {
            "id": record.id,
            "schemaVersion": record.schema_version,
            "sourceFingerprint": record.source_fingerprint,
            "updatedAt": record.updated_at.isoformat(),
            "requirements": [item.as_dict() for item in requirements_from_analysis(record)],
        }
    )


def resume_content_fingerprint(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parse_and_ground_evidence_map(
    raw_content: str,
    requirements: tuple[EvidenceRequirement, ...],
    resume_content: str,
) -> EvidenceMap:
    return _parse_evidence_map(
        raw_content,
        expected_requirements=requirements,
        normalized_resume=_normalize_text(resume_content),
        allowed_requirement_types=frozenset(RequirementType),
        max_resume_evidence_items=MAX_GENERATED_RESUME_EVIDENCE_ITEMS,
    )


def evidence_map_from_stored_json(raw_content: str, *, schema_version: int) -> EvidenceMap:
    if schema_version == 1:
        allowed_requirement_types = frozenset(
            {RequirementType.MUST_HAVE, RequirementType.PREFERRED}
        )
    elif schema_version == EVIDENCE_MAP_SCHEMA_VERSION:
        allowed_requirement_types = frozenset(RequirementType)
    else:
        raise _invalid_response()
    return _parse_evidence_map(
        raw_content,
        expected_requirements=None,
        normalized_resume=None,
        allowed_requirement_types=allowed_requirement_types,
        max_resume_evidence_items=MAX_STORED_RESUME_EVIDENCE_ITEMS,
    )


def _parse_evidence_map(
    raw_content: str,
    *,
    expected_requirements: tuple[EvidenceRequirement, ...] | None,
    normalized_resume: str | None,
    allowed_requirement_types: frozenset[RequirementType],
    max_resume_evidence_items: int,
) -> EvidenceMap:
    try:
        value = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        raise _invalid_response(AnalysisInvalidResponseDiagnostic.INVALID_JSON) from None
    if not isinstance(value, dict) or frozenset(value) != MAP_KEYS:
        raise _invalid_response()
    raw_mappings = value["mappings"]
    if not isinstance(raw_mappings, list) or len(raw_mappings) > MAX_EVIDENCE_MAPPINGS:
        raise _invalid_response()
    mappings = tuple(
        _mapping(
            raw_mapping,
            normalized_resume=normalized_resume,
            allowed_requirement_types=allowed_requirement_types,
            max_resume_evidence_items=max_resume_evidence_items,
        )
        for raw_mapping in raw_mappings
    )
    if expected_requirements is not None:
        actual = tuple(
            EvidenceRequirement(item.requirement_type, item.requirement_text) for item in mappings
        )
        if actual != expected_requirements:
            raise _invalid_response(AnalysisInvalidResponseDiagnostic.REQUIREMENT_MISMATCH)
    return EvidenceMap(mappings=mappings)


def _mapping(
    raw_mapping: Any,
    *,
    normalized_resume: str | None,
    allowed_requirement_types: frozenset[RequirementType],
    max_resume_evidence_items: int,
) -> EvidenceMapping:
    if not isinstance(raw_mapping, dict) or frozenset(raw_mapping) != MAPPING_KEYS:
        raise _invalid_response()
    try:
        requirement_type = RequirementType(raw_mapping["requirementType"])
        coverage = Coverage(raw_mapping["coverage"])
    except (ValueError, TypeError):
        raise _invalid_response() from None
    if requirement_type not in allowed_requirement_types:
        raise _invalid_response()
    requirement_text = _string(raw_mapping["requirementText"])
    reason = _string(raw_mapping["reason"])
    resume_evidence = _resume_evidence(
        raw_mapping["resumeEvidence"],
        normalized_resume=normalized_resume,
        max_items=max_resume_evidence_items,
    )
    if normalized_resume is not None:
        if coverage == Coverage.GAP:
            resume_evidence = ()
        elif not resume_evidence:
            coverage = Coverage.GAP
            reason = GROUNDED_GAP_REASON
    return EvidenceMapping(
        requirement_type=requirement_type,
        requirement_text=requirement_text,
        coverage=coverage,
        resume_evidence=resume_evidence,
        reason=reason,
    )


def _resume_evidence(
    value: Any,
    *,
    normalized_resume: str | None,
    max_items: int,
) -> tuple[ResumeEvidence, ...]:
    if not isinstance(value, list):
        raise _invalid_response()
    if len(value) > max_items:
        raise _invalid_response(AnalysisInvalidResponseDiagnostic.EVIDENCE_LIMIT_EXCEEDED)
    result: list[ResumeEvidence] = []
    seen: set[str] = set()
    for raw_item in value:
        if not isinstance(raw_item, dict) or frozenset(raw_item) != RESUME_EVIDENCE_KEYS:
            raise _invalid_response()
        quote = _string(raw_item["quote"])
        identity = quote.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        if normalized_resume is None or quote in normalized_resume:
            result.append(ResumeEvidence(quote=quote))
    return tuple(result)


def _string(value: Any) -> str:
    if not isinstance(value, str):
        raise _invalid_response()
    normalized = _normalize_text(value)
    if not normalized or len(normalized) > MAX_EVIDENCE_TEXT_LENGTH:
        raise _invalid_response()
    return normalized


def _normalize_text(value: str) -> str:
    return WHITESPACE.sub(" ", value).strip()


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _invalid_response(
    diagnostic_code: AnalysisInvalidResponseDiagnostic = (
        AnalysisInvalidResponseDiagnostic.SCHEMA_MISMATCH
    ),
) -> AnalysisInvalidResponseError:
    return AnalysisInvalidResponseError(
        "AI 返回的证据映射无法验证，请稍后重试",
        diagnostic_code=diagnostic_code,
    )
