from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from jobpilot_api.application.identity_service import IdentityService
from jobpilot_api.config import ApiSettings, AuthSettings
from jobpilot_api.domain.identity import AccountStatus, LocalUser
from jobpilot_api.infrastructure.database.models import IdentityRecord, UserRecord
from jobpilot_api.main import create_app

ISSUER = "https://tenant.example.invalid/"
JWKS_URL = "https://tenant.example.invalid/.well-known/jwks.json"
AUTHORIZE_URL = "https://tenant.example.invalid/authorize"
TOKEN_URL = "https://tenant.example.invalid/oauth/token"
AUDIENCE = "https://api.jobpilot.example.invalid"
EXTENSION_CLIENT_ID = "extension-client-id"
EMAIL_CLAIM = "https://jobpilot.example.invalid/claims/email"
EMAIL_VERIFIED_CLAIM = "https://jobpilot.example.invalid/claims/email_verified"


class FakeExtensionIssuer:
    def __init__(self) -> None:
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_jwk = RSAAlgorithm.to_jwk(self._private_key.public_key(), as_dict=True)
        assert isinstance(public_jwk, dict)
        public_jwk.update({"kid": "key-1", "alg": "RS256", "use": "sig", "key_ops": ["verify"]})
        self._jwks = {"keys": [public_jwk]}
        self.requests: list[httpx2.Request] = []
        self.outage_detail: str | None = None

    def handle_jwks(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self.outage_detail is not None:
            raise httpx2.ConnectError(self.outage_detail, request=request)
        return httpx2.Response(200, json=self._jwks)

    def token(
        self,
        *,
        subject: str = "auth0|subject-1",
        email: str = "Person@Example.COM",
        email_verified: object = True,
    ) -> str:
        now = int(datetime.now(UTC).timestamp())
        return jwt.encode(
            {
                "iss": ISSUER,
                "aud": AUDIENCE,
                "exp": now + 300,
                "iat": now - 1,
                "sub": subject,
                "azp": EXTENSION_CLIENT_ID,
                EMAIL_CLAIM: email,
                EMAIL_VERIFIED_CLAIM: email_verified,
            },
            self._private_key,
            algorithm="RS256",
            headers={"typ": "JWT", "kid": "key-1"},
        )


def _settings(database_url: str) -> ApiSettings:
    return ApiSettings(
        environment="test",
        cors_origins=(),
        auth=AuthSettings(
            issuer=ISSUER,
            jwks_url=JWKS_URL,
            authorize_url=AUTHORIZE_URL,
            token_url=TOKEN_URL,
            audience=AUDIENCE,
            extension_client_id=EXTENSION_CLIENT_ID,
            web_client_id="web-client-id",
            web_client_secret="web-client-secret",
            web_origin="https://api.jobpilot.example.invalid",
            web_callback_url=("https://api.jobpilot.example.invalid/api/v1/auth/web/callback"),
            access_token_email_claim=EMAIL_CLAIM,
            access_token_email_verified_claim=EMAIL_VERIFIED_CLAIM,
        ),
        database_url=database_url,
    )


def _authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def api_context(
    database_url: str,
    migrated_engine: Engine,
) -> Iterator[tuple[TestClient, FakeExtensionIssuer, Engine]]:
    issuer = FakeExtensionIssuer()
    app = create_app(
        _settings(database_url),
        auth_transport=httpx2.MockTransport(issuer.handle_jwks),
    )
    with TestClient(app) as client:
        yield client, issuer, migrated_engine


def test_extension_session_provisions_user_and_reuses_process_scoped_jwks(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
) -> None:
    client, issuer, migrated_engine = api_context
    token = issuer.token()

    established = client.post("/api/v1/auth/session", headers=_authorization(token))
    repeated = client.post("/api/v1/auth/session", headers=_authorization(token))
    current = client.get("/api/v1/auth/me", headers=_authorization(token))

    assert established.status_code == 200
    assert repeated.json() == established.json()
    assert current.status_code == 200
    assert established.json() == current.json()
    assert set(current.json()) == {"data"}
    assert set(current.json()["data"]) == {
        "id",
        "email",
        "displayName",
        "locale",
        "timeZone",
        "createdAt",
        "updatedAt",
    }
    assert current.json()["data"]["email"] == "person@example.com"
    assert current.json()["data"]["displayName"] is None
    assert "set-cookie" not in established.headers
    assert established.headers["Cache-Control"] == "no-store"
    assert current.headers["Cache-Control"] == "no-store"
    assert len(issuer.requests) == 1
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 1
        assert session.scalar(select(func.count()).select_from(IdentityRecord)) == 1


def test_user_view_serializes_database_timestamps_as_utc(
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issuer = FakeExtensionIssuer()
    stored_time = datetime(
        2026,
        8,
        30,
        10,
        15,
        30,
        tzinfo=timezone(timedelta(hours=8)),
    )
    user = LocalUser(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        email="person@example.com",
        display_name=None,
        locale=None,
        time_zone=None,
        account_status=AccountStatus.ACTIVE,
        deletion_requested_at=None,
        created_at=stored_time,
        updated_at=stored_time,
    )
    monkeypatch.setattr(IdentityService, "provision", lambda self, identity: user)
    app = create_app(
        _settings(database_url),
        auth_transport=httpx2.MockTransport(issuer.handle_jwks),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/session",
            headers=_authorization(issuer.token()),
        )

    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(user.id)
    assert response.json()["data"]["createdAt"] == "2026-08-30T02:15:30Z"
    assert response.json()["data"]["updatedAt"] == "2026-08-30T02:15:30Z"


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic credential"},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer token with spaces"},
    ],
)
def test_missing_or_malformed_bearer_is_rejected_before_jwks(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
    headers: dict[str, str],
) -> None:
    client, issuer, _ = api_context

    response = client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.headers["Cache-Control"] == "no-store"
    assert issuer.requests == []


def test_duplicate_authorization_headers_are_rejected_before_jwks(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
) -> None:
    client, issuer, _ = api_context

    response = client.get(
        "/api/v1/auth/me",
        headers=[
            ("Authorization", f"Bearer {issuer.token()}"),
            ("Authorization", "Bearer attacker-controlled-token"),
        ],
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert issuer.requests == []


@pytest.mark.parametrize("include_header", [False, True])
def test_query_token_is_rejected_even_when_a_bearer_header_is_present(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
    include_header: bool,
) -> None:
    client, issuer, _ = api_context
    token = issuer.token()
    headers = _authorization(token) if include_header else {}

    response = client.get(
        "/api/v1/auth/me",
        params={"access_token": "must-not-be-accepted"},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"
    assert "must-not-be-accepted" not in response.text
    assert issuer.requests == []


@pytest.mark.parametrize("cookie_name", ["__Host-jobpilot_session", "jobpilot_dev_session"])
def test_bearer_and_web_session_cookie_are_rejected_as_ambiguous(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
    cookie_name: str,
) -> None:
    client, issuer, _ = api_context
    headers = _authorization(issuer.token())
    headers["Cookie"] = f"{cookie_name}=opaque-cookie"

    response = client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "AMBIGUOUS_CREDENTIALS"
    assert issuer.requests == []


def test_unrelated_cookie_does_not_block_extension_bearer(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
) -> None:
    client, issuer, _ = api_context
    headers = _authorization(issuer.token())
    headers["Cookie"] = "theme=dark"

    response = client.post("/api/v1/auth/session", headers=headers)

    assert response.status_code == 200


@pytest.mark.parametrize("body", [{}, {"email": "attacker@example.com"}, {"userId": "x"}])
def test_extension_session_rejects_every_business_body_before_provisioning(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
    body: dict[str, str],
) -> None:
    client, issuer, migrated_engine = api_context

    response = client.post(
        "/api/v1/auth/session",
        headers=_authorization(issuer.token()),
        json=body,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert issuer.requests == []
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 0


def test_unknown_identity_cannot_use_me_or_provision_a_user(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
) -> None:
    client, issuer, migrated_engine = api_context

    current = client.get(
        "/api/v1/auth/me",
        headers=_authorization(issuer.token(subject="auth0|unknown")),
    )
    updated = client.patch(
        "/api/v1/auth/me",
        headers=_authorization(issuer.token(subject="auth0|unknown")),
        json={"displayName": "Must not provision"},
    )

    assert current.status_code == 401
    assert updated.status_code == 401
    assert current.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 0
        assert session.scalar(select(func.count()).select_from(IdentityRecord)) == 0


def test_same_email_on_a_different_identity_is_a_safe_conflict(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
) -> None:
    client, issuer, migrated_engine = api_context
    first = issuer.token(subject="auth0|first", email="Person@Example.COM")
    second = issuer.token(subject="auth0|second", email=" person@example.com ")

    created = client.post("/api/v1/auth/session", headers=_authorization(first))
    conflict = client.post("/api/v1/auth/session", headers=_authorization(second))

    assert created.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDENTITY_CONFLICT"
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 1
        assert session.scalar(select(func.count()).select_from(IdentityRecord)) == 1


def test_unverified_email_has_a_distinct_forbidden_response_without_writes(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
) -> None:
    client, issuer, migrated_engine = api_context

    response = client.post(
        "/api/v1/auth/session",
        headers=_authorization(issuer.token(email_verified=False)),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "EMAIL_VERIFICATION_REQUIRED"
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 0


def test_email_that_expands_past_storage_limit_is_an_authentication_failure(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
) -> None:
    client, issuer, migrated_engine = api_context

    response = client.post(
        "/api/v1/auth/session",
        headers=_authorization(issuer.token(email=f"{'İ' * 127}@x")),
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 0


def test_provider_outage_is_sanitized_and_does_not_write_identity(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
) -> None:
    client, issuer, migrated_engine = api_context
    issuer.outage_detail = "provider-private-outage-detail"

    response = client.post(
        "/api/v1/auth/session",
        headers=_authorization(issuer.token()),
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "IDENTITY_PROVIDER_UNAVAILABLE"
    assert "provider-private-outage-detail" not in response.text
    with Session(migrated_engine) as session:
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 0


def test_unexpected_identity_service_failure_is_a_sanitized_internal_error(
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    issuer = FakeExtensionIssuer()
    private_detail = "postgresql://user:private-password@database.internal/jobpilot"

    def fail_provision(self: IdentityService, identity: object) -> None:
        raise RuntimeError(private_detail)

    monkeypatch.setattr(IdentityService, "provision", fail_provision)
    error_logger = logging.getLogger("jobpilot_api.api.errors")
    monkeypatch.setattr(error_logger, "disabled", False)
    caplog.set_level(logging.ERROR, logger=error_logger.name)
    origin = "chrome-extension://abcdefghijklmnop"
    settings = _settings(database_url)
    settings = ApiSettings(
        environment=settings.environment,
        cors_origins=(origin,),
        auth=settings.auth,
        database_url=settings.database_url,
    )
    app = create_app(
        settings,
        auth_transport=httpx2.MockTransport(issuer.handle_jwks),
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/auth/session",
            headers={**_authorization(issuer.token()), "Origin": origin},
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert response.headers["X-Request-Id"] == response.json()["error"]["requestId"]
    assert response.headers["access-control-allow-origin"] == origin
    assert private_detail not in response.text
    records = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "api.unexpected_error"
    ]
    assert len(records) == 1
    assert records[0].request_id == response.json()["error"]["requestId"]
    assert records[0].exception_type == "RuntimeError"
    assert response.json()["error"]["requestId"] in caplog.text
    assert "RuntimeError" in caplog.text
    assert private_detail not in caplog.text


def test_error_envelope_echoes_one_valid_request_id(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
) -> None:
    client, _, _ = api_context

    response = client.get(
        "/api/v1/auth/me",
        headers={"X-Request-Id": "request:test-123"},
    )

    assert response.status_code == 401
    assert response.headers["X-Request-Id"] == "request:test-123"
    assert response.json()["error"]["requestId"] == "request:test-123"


def test_invalid_request_id_is_rejected_with_a_generated_safe_id(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
) -> None:
    client, issuer, _ = api_context

    response = client.get(
        "/api/v1/auth/me",
        headers={"X-Request-Id": "invalid request id"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"
    assert response.headers["X-Request-Id"] == response.json()["error"]["requestId"]
    assert response.headers["X-Request-Id"] != "invalid request id"
    assert issuer.requests == []


def test_deletion_pending_identity_cannot_be_reprovisioned_or_read(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
) -> None:
    client, issuer, migrated_engine = api_context
    token = issuer.token(email="original@example.com")
    created = client.post("/api/v1/auth/session", headers=_authorization(token))
    assert created.status_code == 200
    with Session(migrated_engine) as session:
        user = session.scalar(select(UserRecord))
        assert user is not None
        user.account_status = "deletion_pending"
        user.deletion_requested_at = datetime.now(UTC)
        session.commit()

    changed_claim = issuer.token(email="changed@example.com")
    reprovision = client.post(
        "/api/v1/auth/session",
        headers=_authorization(changed_claim),
    )
    current = client.get("/api/v1/auth/me", headers=_authorization(changed_claim))
    updated = client.patch(
        "/api/v1/auth/me",
        headers=_authorization(changed_claim),
        json={"displayName": "Must not reactivate"},
    )

    assert reprovision.status_code == 401
    assert current.status_code == 401
    assert updated.status_code == 401
    with Session(migrated_engine) as session:
        persisted = session.scalar(select(UserRecord))
        assert persisted is not None
        assert persisted.account_status == "deletion_pending"
        assert persisted.email == "original@example.com"
        assert session.scalar(select(func.count()).select_from(UserRecord)) == 1
        assert session.scalar(select(func.count()).select_from(IdentityRecord)) == 1


def test_patch_updates_only_explicit_profile_fields_and_supports_display_name_clear(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
) -> None:
    client, issuer, _ = api_context
    headers = _authorization(issuer.token())
    created = client.post("/api/v1/auth/session", headers=headers)
    assert created.status_code == 200

    updated = client.patch(
        "/api/v1/auth/me",
        headers=headers,
        json={
            "displayName": "Lin",
            "locale": "zh-CN",
            "timeZone": "Asia/Shanghai",
        },
    )
    cleared = client.patch(
        "/api/v1/auth/me",
        headers=headers,
        json={"displayName": None},
    )
    current = client.get("/api/v1/auth/me", headers=headers)

    assert updated.status_code == 200
    assert updated.json()["data"]["displayName"] == "Lin"
    assert cleared.status_code == 200
    assert current.json()["data"]["displayName"] is None
    assert current.json()["data"]["locale"] == "zh-CN"
    assert current.json()["data"]["timeZone"] == "Asia/Shanghai"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"email": "attacker@example.com"},
        {"display_name": "internal-field-name"},
        {"time_zone": "Asia/Shanghai"},
        {"displayName": "x" * 101},
        {"locale": "not_a_locale"},
        {"locale": None},
        {"timeZone": "Not/A_Real_Zone"},
        {"timeZone": "Asia\\Shanghai"},
        {"timeZone": None},
    ],
)
def test_patch_rejects_empty_unknown_or_invalid_profile_fields(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
    body: dict[str, object],
) -> None:
    client, issuer, _ = api_context
    headers = _authorization(issuer.token())
    assert client.post("/api/v1/auth/session", headers=headers).status_code == 200

    response = client.patch("/api/v1/auth/me", headers=headers, json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_me_does_not_synchronize_changed_email_claim_outside_session_boundary(
    api_context: tuple[TestClient, FakeExtensionIssuer, Engine],
) -> None:
    client, issuer, _ = api_context
    original = issuer.token(email="original@example.com")
    assert client.post("/api/v1/auth/session", headers=_authorization(original)).status_code == 200

    changed_claim = issuer.token(email="changed@example.com")
    current = client.get("/api/v1/auth/me", headers=_authorization(changed_claim))

    assert current.status_code == 200
    assert current.json()["data"]["email"] == "original@example.com"
