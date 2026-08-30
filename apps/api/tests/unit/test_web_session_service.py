from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from jobpilot_api.application.web_session_service import (
    CSRF_DERIVATION_CONTEXT,
    InvalidSessionSecretError,
    WebSessionService,
)
from jobpilot_api.domain.web_session import WebSession


class RecordingWebSessionRepository:
    def __init__(self) -> None:
        self.create_call: dict[str, object] | None = None

    def create(self, **values: object) -> WebSession:
        self.create_call = values
        return WebSession(
            id=uuid4(),
            user_id=values["user_id"],  # type: ignore[arg-type]
            identity_issuer=values["identity_issuer"],  # type: ignore[arg-type]
            identity_subject=values["identity_subject"],  # type: ignore[arg-type]
            csrf_token_hash=values["csrf_token_hash"],  # type: ignore[arg-type]
            created_at=values["created_at"],  # type: ignore[arg-type]
            last_used_at=values["last_used_at"],  # type: ignore[arg-type]
            idle_expires_at=values["idle_expires_at"],  # type: ignore[arg-type]
            absolute_expires_at=values["absolute_expires_at"],  # type: ignore[arg-type]
            revoked_at=None,
        )


class RecordingWebSessionUnitOfWork:
    def __init__(self, repository: RecordingWebSessionRepository) -> None:
        self.sessions = repository
        self.commit_count = 0

    def __enter__(self) -> RecordingWebSessionUnitOfWork:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def commit(self) -> None:
        self.commit_count += 1


def test_issue_derives_session_bound_csrf_and_persists_only_hashes() -> None:
    raw_entropy = bytes(range(32))
    now = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)
    user_id = uuid4()
    repository = RecordingWebSessionRepository()
    unit_of_work = RecordingWebSessionUnitOfWork(repository)
    service = WebSessionService(
        lambda: unit_of_work,
        token_factory=lambda: raw_entropy,
        clock=lambda: now,
        idle_timeout=timedelta(days=7),
        absolute_timeout=timedelta(days=30),
    )

    issued = service.issue(
        user_id=user_id,
        identity_issuer="https://tenant.example.invalid/",
        identity_subject="auth0|subject-1",
    )

    expected_session_secret = base64.urlsafe_b64encode(raw_entropy).rstrip(b"=").decode()
    expected_csrf_token = (
        base64.urlsafe_b64encode(hmac.digest(raw_entropy, CSRF_DERIVATION_CONTEXT, hashlib.sha256))
        .rstrip(b"=")
        .decode()
    )
    assert issued.session_secret == expected_session_secret
    assert issued.csrf_token == expected_csrf_token
    assert repository.create_call == {
        "user_id": user_id,
        "identity_issuer": "https://tenant.example.invalid/",
        "identity_subject": "auth0|subject-1",
        "session_token_hash": hashlib.sha256(expected_session_secret.encode()).digest(),
        "csrf_token_hash": hashlib.sha256(expected_csrf_token.encode()).digest(),
        "created_at": now,
        "last_used_at": now,
        "idle_expires_at": now + timedelta(days=7),
        "absolute_expires_at": now + timedelta(days=30),
    }
    assert expected_session_secret not in repr(issued)
    assert expected_csrf_token not in repr(issued)
    assert unit_of_work.commit_count == 1


def test_issue_rejects_non_256_bit_entropy_before_opening_unit_of_work() -> None:
    unit_of_work_opened = False

    def open_unit_of_work() -> RecordingWebSessionUnitOfWork:
        nonlocal unit_of_work_opened
        unit_of_work_opened = True
        return RecordingWebSessionUnitOfWork(RecordingWebSessionRepository())

    service = WebSessionService(
        open_unit_of_work,
        token_factory=lambda: b"too-short",
    )

    with pytest.raises(InvalidSessionSecretError):
        service.issue(
            user_id=uuid4(),
            identity_issuer="https://tenant.example.invalid/",
            identity_subject="auth0|subject-1",
        )

    assert unit_of_work_opened is False
