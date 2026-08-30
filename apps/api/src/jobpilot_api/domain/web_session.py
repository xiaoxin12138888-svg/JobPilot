from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from jobpilot_api.domain.identity import AuthenticatedUser


@dataclass(frozen=True, slots=True)
class WebSession:
    id: UUID
    user_id: UUID
    identity_issuer: str
    identity_subject: str
    csrf_token_hash: bytes = field(repr=False)
    created_at: datetime
    last_used_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class LoginTransaction:
    id: UUID
    browser_handle_hash: bytes = field(repr=False)
    state_hash: bytes = field(repr=False)
    nonce_hash: bytes = field(repr=False)
    pkce_verifier: str = field(repr=False)
    intent: str
    return_to: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class IssuedWebSession:
    session: WebSession
    session_secret: str = field(repr=False)
    csrf_token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class AuthenticatedWebSession:
    authenticated_user: AuthenticatedUser
    csrf_token: str = field(repr=False)
