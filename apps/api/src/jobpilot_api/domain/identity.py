from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class AccountStatus(StrEnum):
    ACTIVE = "active"
    DELETION_PENDING = "deletion_pending"


@dataclass(frozen=True, slots=True)
class VerifiedProviderIdentity:
    issuer: str
    subject: str
    verified_email: str
    authorized_party: str
    authentication_time: datetime | None = None

    def __post_init__(self) -> None:
        for field_name in ("issuer", "subject", "verified_email", "authorized_party"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")
        if self.authentication_time is not None and self.authentication_time.utcoffset() is None:
            raise ValueError("authentication_time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class LocalUser:
    id: UUID
    email: str
    display_name: str | None
    locale: str | None
    time_zone: str | None
    account_status: AccountStatus
    deletion_requested_at: datetime | None
    created_at: datetime
    updated_at: datetime
