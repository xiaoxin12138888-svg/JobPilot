from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from jobpilot_api.domain.errors import DomainValidationError
from jobpilot_api.domain.jobs import CONTROL_CHARACTER_TRANSLATION

MAX_COLLECTION_ITEMS = 20
MAX_SHORT_TEXT_LENGTH = 300
MAX_CONTACT_TEXT_LENGTH = 320
MAX_DESCRIPTION_LENGTH = 20_000
MAX_URL_LENGTH = 2_048
MONTH_PATTERN = re.compile(r"[0-9]{4}-(?:0[1-9]|1[0-2])\Z")


@dataclass(frozen=True, slots=True)
class PersonalDetails:
    name: str | None
    phone: str | None
    email: str | None
    current_city: str | None


@dataclass(frozen=True, slots=True)
class EducationEntry:
    school: str | None
    major: str | None
    degree: str | None
    start: str | None
    end: str | None


@dataclass(frozen=True, slots=True)
class ExperienceEntry:
    company: str | None
    position: str | None
    start: str | None
    end: str | None
    description: str | None


@dataclass(frozen=True, slots=True)
class ProfileLinks:
    github: str | None
    portfolio: str | None
    homepage: str | None


@dataclass(frozen=True, slots=True)
class AutofillProfileDraft:
    personal: PersonalDetails
    education: tuple[EducationEntry, ...]
    experience: tuple[ExperienceEntry, ...]
    links: ProfileLinks

    @classmethod
    def create(
        cls,
        *,
        personal: Mapping[str, object],
        education: Sequence[Mapping[str, object]],
        experience: Sequence[Mapping[str, object]],
        links: Mapping[str, object],
    ) -> AutofillProfileDraft:
        personal_details = _personal_details(personal)
        education_entries = _education_entries(education)
        experience_entries = _experience_entries(experience)
        profile_links = _profile_links(links)

        draft = cls(
            personal=personal_details,
            education=education_entries,
            experience=experience_entries,
            links=profile_links,
        )
        if not _has_facts(draft):
            raise DomainValidationError("autofillProfile: must contain at least one fact")
        return draft


@dataclass(frozen=True, slots=True)
class AutofillProfile:
    personal: PersonalDetails
    education: tuple[EducationEntry, ...]
    experience: tuple[ExperienceEntry, ...]
    links: ProfileLinks
    created_at: datetime
    updated_at: datetime


def _personal_details(value: Mapping[str, object]) -> PersonalDetails:
    _require_mapping("personal", value)
    return PersonalDetails(
        name=_optional_text("personal.name", value.get("name"), MAX_SHORT_TEXT_LENGTH),
        phone=_optional_text("personal.phone", value.get("phone"), MAX_CONTACT_TEXT_LENGTH),
        email=_optional_text("personal.email", value.get("email"), MAX_CONTACT_TEXT_LENGTH),
        current_city=_optional_text(
            "personal.currentCity",
            value.get("current_city", value.get("currentCity")),
            MAX_SHORT_TEXT_LENGTH,
        ),
    )


def _education_entries(value: Sequence[Mapping[str, object]]) -> tuple[EducationEntry, ...]:
    items = _require_collection("education", value)
    entries: list[EducationEntry] = []
    for index, item in enumerate(items):
        field = f"education[{index}]"
        _require_mapping(field, item)
        entry = EducationEntry(
            school=_optional_text(f"{field}.school", item.get("school"), MAX_SHORT_TEXT_LENGTH),
            major=_optional_text(f"{field}.major", item.get("major"), MAX_SHORT_TEXT_LENGTH),
            degree=_optional_text(f"{field}.degree", item.get("degree"), MAX_SHORT_TEXT_LENGTH),
            start=_optional_month(f"{field}.start", item.get("start")),
            end=_optional_month(f"{field}.end", item.get("end")),
        )
        if not any((entry.school, entry.major, entry.degree, entry.start, entry.end)):
            raise DomainValidationError(f"{field}: must contain at least one fact")
        entries.append(entry)
    return tuple(entries)


def _experience_entries(value: Sequence[Mapping[str, object]]) -> tuple[ExperienceEntry, ...]:
    items = _require_collection("experience", value)
    entries: list[ExperienceEntry] = []
    for index, item in enumerate(items):
        field = f"experience[{index}]"
        _require_mapping(field, item)
        entry = ExperienceEntry(
            company=_optional_text(f"{field}.company", item.get("company"), MAX_SHORT_TEXT_LENGTH),
            position=_optional_text(
                f"{field}.position", item.get("position"), MAX_SHORT_TEXT_LENGTH
            ),
            start=_optional_month(f"{field}.start", item.get("start")),
            end=_optional_month(f"{field}.end", item.get("end")),
            description=_optional_text(
                f"{field}.description", item.get("description"), MAX_DESCRIPTION_LENGTH
            ),
        )
        if not any((entry.company, entry.position, entry.start, entry.end, entry.description)):
            raise DomainValidationError(f"{field}: must contain at least one fact")
        entries.append(entry)
    return tuple(entries)


def _profile_links(value: Mapping[str, object]) -> ProfileLinks:
    _require_mapping("links", value)
    return ProfileLinks(
        github=_optional_http_url("links.github", value.get("github")),
        portfolio=_optional_http_url("links.portfolio", value.get("portfolio")),
        homepage=_optional_http_url("links.homepage", value.get("homepage")),
    )


def _require_mapping(field: str, value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise DomainValidationError(f"{field}: must be an object")
    return value


def _require_collection(field: str, value: object) -> Sequence[Mapping[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise DomainValidationError(f"{field}: must be an array")
    if len(value) > MAX_COLLECTION_ITEMS:
        raise DomainValidationError(f"{field}: must contain at most {MAX_COLLECTION_ITEMS} entries")
    return value


def _optional_text(field: str, value: object, maximum: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DomainValidationError(f"{field}: must be text")
    cleaned = _plain_text(value).strip()
    if not cleaned:
        return None
    if len(cleaned) > maximum:
        raise DomainValidationError(f"{field}: must be at most {maximum} characters")
    return cleaned


def _optional_month(field: str, value: object) -> str | None:
    cleaned = _optional_text(field, value, 7)
    if cleaned is not None and MONTH_PATTERN.fullmatch(cleaned) is None:
        raise DomainValidationError(f"{field}: must use YYYY-MM")
    return cleaned


def _optional_http_url(field: str, value: object) -> str | None:
    cleaned = _optional_text(field, value, MAX_URL_LENGTH)
    if cleaned is None:
        return None
    try:
        parsed = urlsplit(cleaned)
        port = parsed.port
    except ValueError:
        raise DomainValidationError(f"{field}: must be a valid HTTP or HTTPS URL") from None
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise DomainValidationError(f"{field}: must be an HTTP or HTTPS URL without credentials")
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower()
    if ":" in hostname:
        hostname = f"[{hostname}]"
    include_port = port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    )
    netloc = f"{hostname}:{port}" if include_port else hostname
    return urlunsplit((scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def _has_facts(draft: AutofillProfileDraft) -> bool:
    return any(
        (
            draft.personal.name,
            draft.personal.phone,
            draft.personal.email,
            draft.personal.current_city,
            draft.education,
            draft.experience,
            draft.links.github,
            draft.links.portfolio,
            draft.links.homepage,
        )
    )


def _plain_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").translate(CONTROL_CHARACTER_TRANSLATION)
