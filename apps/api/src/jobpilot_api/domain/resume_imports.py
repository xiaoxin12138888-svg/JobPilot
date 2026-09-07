from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from jobpilot_api.domain.autofill_profiles import (
    AutofillProfile,
    AutofillProfileDraft,
    EducationEntry,
    ExperienceEntry,
    PersonalDetails,
    ProfileLinks,
)
from jobpilot_api.domain.errors import DomainError
from jobpilot_api.domain.resume_versions import ResumeVersion

MAX_RESUME_FILE_BYTES = 10 * 1024 * 1024
MAX_RESUME_MULTIPART_BODY_BYTES = MAX_RESUME_FILE_BYTES + 64 * 1024
MAX_EXTRACTED_TEXT_LENGTH = 100_000
MAX_PDF_PAGES = 100
MIN_PDF_NON_WHITESPACE_CHARACTERS = 20
RESUME_PARSE_TIMEOUT_SECONDS = 10.0


class ResumeFileType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"


class DocumentBlockKind(StrEnum):
    TEXT = "TEXT"
    TABLE_ROW = "TABLE_ROW"
    HEADING = "HEADING"


class ResumeSectionKind(StrEnum):
    BASIC = "BASIC"
    EDUCATION = "EDUCATION"
    EXPERIENCE = "EXPERIENCE"
    PROJECT = "PROJECT"
    SKILLS = "SKILLS"
    CERTIFICATES = "CERTIFICATES"
    AWARDS = "AWARDS"
    OTHER = "OTHER"


class ResumeImportError(DomainError):
    def __init__(self, code: str, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class DocumentBlock:
    kind: DocumentBlockKind
    text: str


@dataclass(frozen=True, slots=True)
class ResumeImportWarning:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ParsedResumeDocument:
    file_type: ResumeFileType
    raw_text: str
    blocks: tuple[DocumentBlock, ...]
    warnings: tuple[ResumeImportWarning, ...] = ()
    page_count: int | None = None


@dataclass(frozen=True, slots=True)
class ResumeSection:
    kind: ResumeSectionKind
    heading: str | None
    text: str


@dataclass(frozen=True, slots=True)
class ResumeProfileCandidates:
    personal: PersonalDetails
    education: tuple[EducationEntry, ...]
    experience: tuple[ExperienceEntry, ...]
    links: ProfileLinks


@dataclass(frozen=True, slots=True)
class ResumeImportPreview:
    file_type: ResumeFileType
    extracted_text: str
    blocks: tuple[DocumentBlock, ...]
    sections: tuple[ResumeSection, ...]
    profile_candidates: ResumeProfileCandidates
    warnings: tuple[ResumeImportWarning, ...]
    page_count: int | None


@dataclass(frozen=True, slots=True)
class ResumeProfileImportPatch:
    values: AutofillProfileDraft
    selected_personal: frozenset[str]
    selected_links: frozenset[str]

    @classmethod
    def create(
        cls,
        *,
        personal: Mapping[str, object],
        education: Sequence[Mapping[str, object]],
        experience: Sequence[Mapping[str, object]],
        links: Mapping[str, object],
    ) -> ResumeProfileImportPatch:
        personal_keys = frozenset(personal)
        link_keys = frozenset(links)
        allowed_personal = {"name", "phone", "email", "currentCity", "current_city"}
        if not personal_keys.issubset(allowed_personal):
            raise ResumeImportError("VALIDATION_ERROR", "求职资料包含未知基本字段")
        if not link_keys.issubset({"github", "portfolio", "homepage"}):
            raise ResumeImportError("VALIDATION_ERROR", "求职资料包含未知链接字段")
        if any(not isinstance(value, str) or not value.strip() for value in personal.values()):
            raise ResumeImportError("VALIDATION_ERROR", "已选择的基本资料不得为空")
        if any(not isinstance(value, str) or not value.strip() for value in links.values()):
            raise ResumeImportError("VALIDATION_ERROR", "已选择的链接不得为空")
        values = AutofillProfileDraft.create(
            personal=personal,
            education=education,
            experience=experience,
            links=links,
        )
        selected_personal = frozenset(
            "current_city" if key == "currentCity" else key for key in personal_keys
        )
        return cls(values, selected_personal, link_keys)


@dataclass(frozen=True, slots=True)
class ResumeImportConfirmation:
    resume_version: ResumeVersion | None
    profile: AutofillProfile | None


def merge_autofill_profile(
    current: AutofillProfile | AutofillProfileDraft | None,
    patch: ResumeProfileImportPatch,
) -> AutofillProfileDraft:
    personal: dict[str, object] = {
        "name": current.personal.name if current else None,
        "phone": current.personal.phone if current else None,
        "email": current.personal.email if current else None,
        "currentCity": current.personal.current_city if current else None,
    }
    imported_personal = {
        "name": patch.values.personal.name,
        "phone": patch.values.personal.phone,
        "email": patch.values.personal.email,
        "current_city": patch.values.personal.current_city,
    }
    for field in patch.selected_personal:
        output_field = "currentCity" if field == "current_city" else field
        personal[output_field] = imported_personal[field]

    links: dict[str, object] = {
        "github": current.links.github if current else None,
        "portfolio": current.links.portfolio if current else None,
        "homepage": current.links.homepage if current else None,
    }
    for field in patch.selected_links:
        links[field] = getattr(patch.values.links, field)

    existing_education = list(current.education) if current else []
    existing_experience = list(current.experience) if current else []
    return AutofillProfileDraft.create(
        personal=personal,
        education=[
            _education_mapping(item) for item in (*existing_education, *patch.values.education)
        ],
        experience=[
            _experience_mapping(item) for item in (*existing_experience, *patch.values.experience)
        ],
        links=links,
    )


def _education_mapping(item: EducationEntry) -> dict[str, object]:
    return {
        "school": item.school,
        "major": item.major,
        "degree": item.degree,
        "start": item.start,
        "end": item.end,
    }


def _experience_mapping(item: ExperienceEntry) -> dict[str, object]:
    return {
        "company": item.company,
        "position": item.position,
        "start": item.start,
        "end": item.end,
        "description": item.description,
    }


_HEADING_ALIASES = {
    "基本信息": ResumeSectionKind.BASIC,
    "个人信息": ResumeSectionKind.BASIC,
    "basic information": ResumeSectionKind.BASIC,
    "personal information": ResumeSectionKind.BASIC,
    "教育经历": ResumeSectionKind.EDUCATION,
    "教育背景": ResumeSectionKind.EDUCATION,
    "学习经历": ResumeSectionKind.EDUCATION,
    "education": ResumeSectionKind.EDUCATION,
    "实习经历": ResumeSectionKind.EXPERIENCE,
    "工作经历": ResumeSectionKind.EXPERIENCE,
    "实践经历": ResumeSectionKind.EXPERIENCE,
    "experience": ResumeSectionKind.EXPERIENCE,
    "work experience": ResumeSectionKind.EXPERIENCE,
    "项目经历": ResumeSectionKind.PROJECT,
    "项目经验": ResumeSectionKind.PROJECT,
    "projects": ResumeSectionKind.PROJECT,
    "project experience": ResumeSectionKind.PROJECT,
    "专业技能": ResumeSectionKind.SKILLS,
    "技能": ResumeSectionKind.SKILLS,
    "skills": ResumeSectionKind.SKILLS,
    "技能证书": ResumeSectionKind.CERTIFICATES,
    "证书": ResumeSectionKind.CERTIFICATES,
    "certificates": ResumeSectionKind.CERTIFICATES,
    "荣誉奖项": ResumeSectionKind.AWARDS,
    "获奖情况": ResumeSectionKind.AWARDS,
    "awards": ResumeSectionKind.AWARDS,
}
_EMAIL_PATTERN = re.compile(r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,63}(?![\w.-])", re.I)
_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d(?:[- ]?\d){8}(?!\d)")
_MONTH_PATTERN = re.compile(r"(?<!\d)((?:19|20)\d{2})[./-](0?[1-9]|1[0-2])(?!\d)")
_LABEL_PATTERN = re.compile(
    r"^(学校|院校|专业|学历|学位|公司|单位|职位|岗位|时间)\s*[：:]\s*(.+)$",
    re.I,
)
_SCHOOL_PATTERN = re.compile(r"(?:大学|学院|学校|university|college|institute)$", re.I)
_COMPANY_PATTERN = re.compile(
    r"(?:公司|集团|事务所|研究院|实验室|corp(?:oration)?|company|co\.?|ltd\.?|inc\.?)$",
    re.I,
)
_DEGREE_VALUES = {
    "专科",
    "大专",
    "本科",
    "学士",
    "硕士",
    "博士",
    "associate",
    "bachelor",
    "master",
    "phd",
}


def build_resume_import_preview(document: ParsedResumeDocument) -> ResumeImportPreview:
    blocks = tuple(_classify_block(block) for block in document.blocks if block.text.strip())
    sections = _sections(blocks)
    candidates = ResumeProfileCandidates(
        personal=_personal_candidates(sections, blocks),
        education=_education_candidates(sections),
        experience=_experience_candidates(sections),
        links=_link_candidates(document.raw_text),
    )
    warnings = list(document.warnings)
    if not candidates.education:
        warnings.append(ResumeImportWarning("EDUCATION_NOT_DETECTED", "未识别到明确的教育经历"))
    if not candidates.experience:
        warnings.append(
            ResumeImportWarning("EXPERIENCE_NOT_DETECTED", "未识别到明确的工作或实习经历")
        )
    if not any((candidates.personal.name, candidates.personal.phone, candidates.personal.email)):
        warnings.append(ResumeImportWarning("BASIC_NOT_DETECTED", "未识别到明确的基本资料"))
    return ResumeImportPreview(
        file_type=document.file_type,
        extracted_text=document.raw_text,
        blocks=blocks,
        sections=sections,
        profile_candidates=candidates,
        warnings=tuple(dict.fromkeys(warnings)),
        page_count=document.page_count,
    )


def _classify_block(block: DocumentBlock) -> DocumentBlock:
    if _heading_kind(block.text) is not None:
        return DocumentBlock(DocumentBlockKind.HEADING, block.text.strip())
    return DocumentBlock(block.kind, block.text.strip())


def _heading_kind(text: str) -> ResumeSectionKind | None:
    normalized = text.strip().rstrip(":：").strip().casefold()
    return _HEADING_ALIASES.get(normalized)


def _sections(blocks: tuple[DocumentBlock, ...]) -> tuple[ResumeSection, ...]:
    sections: list[ResumeSection] = []
    current_kind = ResumeSectionKind.OTHER
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if current_heading is not None or current_lines:
            sections.append(
                ResumeSection(current_kind, current_heading, "\n".join(current_lines).strip())
            )

    for block in blocks:
        heading_kind = _heading_kind(block.text)
        if heading_kind is not None:
            flush()
            current_kind = heading_kind
            current_heading = block.text
            current_lines = []
        else:
            current_lines.append(block.text)
    flush()
    return tuple(sections)


def _personal_candidates(
    sections: tuple[ResumeSection, ...], blocks: tuple[DocumentBlock, ...]
) -> PersonalDetails:
    contact_text = "\n".join(block.text for block in blocks[:30])
    email_match = _EMAIL_PATTERN.search(contact_text)
    phone_match = _PHONE_PATTERN.search(contact_text)
    basic = next((section for section in sections if section.kind == ResumeSectionKind.BASIC), None)
    name_lines = (
        basic.text.splitlines() if basic is not None else [block.text for block in blocks[:8]]
    )
    name = _candidate_name(name_lines, email_match is not None or phone_match is not None)
    phone = re.sub(r"[^+\d]", "", phone_match.group(0)) if phone_match else None
    return PersonalDetails(
        name=name,
        phone=phone,
        email=email_match.group(0) if email_match else None,
        current_city=None,
    )


def _candidate_name(lines: list[str], has_contact: bool) -> str | None:
    if not has_contact:
        return None
    for line in lines[:8]:
        value = line.strip()
        if _heading_kind(value) is not None or any(mark in value for mark in ("@", ":", "：")):
            continue
        if re.fullmatch(r"[\u3400-\u9fff·]{2,8}", value):
            return value
        if re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,39}", value) and len(value.split()) <= 5:
            return value
    return None


def _education_candidates(sections: tuple[ResumeSection, ...]) -> tuple[EducationEntry, ...]:
    entries: list[EducationEntry] = []
    for section in sections:
        if section.kind != ResumeSectionKind.EDUCATION:
            continue
        for facts in _fact_groups(section.text, start_labels={"学校", "院校"}):
            school = facts.get("学校") or facts.get("院校")
            major = facts.get("专业")
            degree = facts.get("学历") or facts.get("学位")
            start, end = _months(facts.get("时间", ""))
            if any((school, major, degree, start, end)):
                entries.append(EducationEntry(school, major, degree, start, end))
        entries.extend(_unlabeled_education_entries(section.text))
    return tuple(entries)


def _experience_candidates(sections: tuple[ResumeSection, ...]) -> tuple[ExperienceEntry, ...]:
    entries: list[ExperienceEntry] = []
    for section in sections:
        if section.kind != ResumeSectionKind.EXPERIENCE:
            continue
        for facts in _fact_groups(section.text, start_labels={"公司", "单位"}):
            company = facts.get("公司") or facts.get("单位")
            position = facts.get("职位") or facts.get("岗位")
            start, end = _months(facts.get("时间", ""))
            if any((company, position, start, end)):
                entries.append(ExperienceEntry(company, position, start, end, None))
        entries.extend(_unlabeled_experience_entries(section.text))
    return tuple(entries)


def _unlabeled_education_entries(text: str) -> tuple[EducationEntry, ...]:
    entries: list[EducationEntry] = []
    for segments in _unlabeled_table_rows(text):
        school = next((value for value in segments if _SCHOOL_PATTERN.search(value)), None)
        date_text = next((value for value in segments if _MONTH_PATTERN.search(value)), None)
        if school is None or date_text is None:
            continue
        degree = next((value for value in segments if value.casefold() in _DEGREE_VALUES), None)
        major = next(
            (
                value
                for value in segments
                if value not in {school, date_text, degree} and not _MONTH_PATTERN.search(value)
            ),
            None,
        )
        start, end = _months(date_text)
        entries.append(EducationEntry(school, major, degree, start, end))
    return tuple(entries)


def _unlabeled_experience_entries(text: str) -> tuple[ExperienceEntry, ...]:
    entries: list[ExperienceEntry] = []
    for segments in _unlabeled_table_rows(text):
        company = next((value for value in segments if _COMPANY_PATTERN.search(value)), None)
        date_text = next((value for value in segments if _MONTH_PATTERN.search(value)), None)
        if company is None or date_text is None:
            continue
        position = next(
            (
                value
                for value in segments
                if value not in {company, date_text} and not _MONTH_PATTERN.search(value)
            ),
            None,
        )
        start, end = _months(date_text)
        entries.append(ExperienceEntry(company, position, start, end, None))
    return tuple(entries)


def _unlabeled_table_rows(text: str) -> tuple[tuple[str, ...], ...]:
    rows: list[tuple[str, ...]] = []
    for line in text.splitlines():
        if "|" not in line:
            continue
        segments = tuple(value.strip() for value in line.split("|") if value.strip())
        if len(segments) >= 2 and not any(_LABEL_PATTERN.fullmatch(value) for value in segments):
            rows.append(segments)
    return tuple(rows)


def _fact_groups(text: str, *, start_labels: set[str]) -> tuple[dict[str, str], ...]:
    groups: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in text.splitlines():
        for segment in re.split(r"\s*\|\s*", line):
            match = _LABEL_PATTERN.fullmatch(segment.strip())
            if match is None:
                continue
            label, value = match.group(1), match.group(2).strip()
            if label in start_labels and current:
                groups.append(current)
                current = {}
            current[label] = value
    if current:
        groups.append(current)
    return tuple(groups)


def _months(text: str) -> tuple[str | None, str | None]:
    values = [
        f"{match.group(1)}-{int(match.group(2)):02d}" for match in _MONTH_PATTERN.finditer(text)
    ]
    return (values[0] if values else None, values[1] if len(values) > 1 else None)


def _link_candidates(text: str) -> ProfileLinks:
    match = re.search(r"https://github\.com/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?", text, re.I)
    return ProfileLinks(github=match.group(0) if match else None, portfolio=None, homepage=None)
