from __future__ import annotations

import base64
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from uuid import UUID

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from jobpilot_api.application.web_session_service import (
    WebSessionPersistenceError,
    derive_csrf_token,
    hash_browser_secret,
)
from jobpilot_api.config import ApiSettings, AuthSettings
from jobpilot_api.infrastructure.database.models import (
    IdentityRecord,
    UserRecord,
    WebSessionRecord,
)
from jobpilot_api.infrastructure.database.web_session_repository import (
    SqlAlchemyWebSessionUnitOfWork,
)
from jobpilot_api.main import create_app

ISSUER = "https://tenant.example.invalid/"
JWKS_URL = "https://tenant.example.invalid/.well-known/jwks.json"
AUTHORIZE_URL = "https://tenant.example.invalid/authorize"
TOKEN_URL = "https://tenant.example.invalid/oauth/token"
AUDIENCE = "https://api.jobpilot.example.invalid"
EXTENSION_CLIENT_ID = "extension-client-id"
WEB_CLIENT_ID = "web-client-id"
EMAIL_CLAIM = "https://jobpilot.example.invalid/claims/email"
EMAIL_VERIFIED_CLAIM = "https://jobpilot.example.invalid/claims/email_verified"


@dataclass(frozen=True, slots=True)
class WebDeployment:
    environment: str
    web_origin: str
    api_origin: str
    session_cookie: str
    other_session_cookie: str
    secure: bool

    @property
    def callback_url(self) -> str:
        return f"{self.api_origin}/api/v1/auth/web/callback"


PRODUCTION = WebDeployment(
    environment="production",
    web_origin="https://jobpilot.example.invalid:444",
    api_origin="https://jobpilot.example.invalid",
    session_cookie="__Host-jobpilot_session",
    other_session_cookie="jobpilot_dev_session",
    secure=True,
)
LOOPBACK_DEVELOPMENT = WebDeployment(
    environment="development",
    web_origin="http://localhost:5173",
    api_origin="http://localhost:8000",
    session_cookie="jobpilot_dev_session",
    other_session_cookie="__Host-jobpilot_session",
    secure=False,
)


class FakeExtensionIssuer:
    def __init__(self) -> None:
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_jwk = RSAAlgorithm.to_jwk(self._private_key.public_key(), as_dict=True)
        assert isinstance(public_jwk, dict)
        public_jwk.update({"kid": "key-1", "alg": "RS256", "use": "sig", "key_ops": ["verify"]})
        self._jwks = {"keys": [public_jwk]}
        self.requests: list[httpx2.Request] = []

    def handle_jwks(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return httpx2.Response(200, json=self._jwks)

    def token(self) -> str:
        now = int(datetime.now(UTC).timestamp())
        return jwt.encode(
            {
                "iss": ISSUER,
                "aud": AUDIENCE,
                "exp": now + 300,
                "iat": now - 1,
                "sub": "auth0|same-user",
                "azp": EXTENSION_CLIENT_ID,
                EMAIL_CLAIM: "person@example.com",
                EMAIL_VERIFIED_CLAIM: True,
            },
            self._private_key,
            algorithm="RS256",
            headers={"typ": "JWT", "kid": "key-1"},
        )


@dataclass(frozen=True, slots=True)
class SeededSession:
    user_id: UUID
    session_id: UUID
    session_secret: str
    csrf_token: str


@dataclass(slots=True)
class ApiContext:
    client: TestClient
    issuer: FakeExtensionIssuer
    engine: Engine
    deployment: WebDeployment
    seeded: SeededSession


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    last_used_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None


def _opaque(byte: int) -> str:
    return base64.urlsafe_b64encode(bytes([byte]) * 32).rstrip(b"=").decode("ascii")


def _settings(database_url: str, deployment: WebDeployment) -> ApiSettings:
    cors_origins = (
        (deployment.web_origin,) if deployment.web_origin != deployment.api_origin else ()
    )
    return ApiSettings(
        environment=deployment.environment,
        cors_origins=cors_origins,
        auth=AuthSettings(
            issuer=ISSUER,
            jwks_url=JWKS_URL,
            authorize_url=AUTHORIZE_URL,
            token_url=TOKEN_URL,
            audience=AUDIENCE,
            extension_client_id=EXTENSION_CLIENT_ID,
            web_client_id=WEB_CLIENT_ID,
            web_client_secret="server-only-test-secret",
            web_origin=deployment.web_origin,
            web_callback_url=deployment.callback_url,
            access_token_email_claim=EMAIL_CLAIM,
            access_token_email_verified_claim=EMAIL_VERIFIED_CLAIM,
            web_session_idle_seconds=604_800,
            web_session_absolute_seconds=2_592_000,
        ),
        database_url=database_url,
    )


def _seed_session(engine: Engine) -> SeededSession:
    now = datetime.now(UTC)
    session_secret = _opaque(0x31)
    csrf_token = derive_csrf_token(session_secret)
    with Session(engine) as database:
        user = UserRecord(
            email="person@example.com",
            display_name="Existing User",
            locale="zh-CN",
            time_zone="Asia/Shanghai",
            created_at=now - timedelta(days=30),
            updated_at=now - timedelta(days=1),
        )
        database.add(user)
        database.flush()
        identity = IdentityRecord(
            user_id=user.id,
            issuer=ISSUER,
            subject="auth0|same-user",
            created_at=now - timedelta(days=30),
            updated_at=now - timedelta(days=30),
        )
        database.add(identity)
        database.flush()
        web_session = WebSessionRecord(
            user_id=user.id,
            identity_id=identity.id,
            session_token_hash=hash_browser_secret(session_secret),
            csrf_token_hash=hash_browser_secret(csrf_token),
            created_at=now - timedelta(hours=2),
            last_used_at=now - timedelta(hours=1),
            idle_expires_at=now + timedelta(hours=1),
            absolute_expires_at=now + timedelta(days=7),
        )
        database.add(web_session)
        database.commit()
        return SeededSession(user.id, web_session.id, session_secret, csrf_token)


@contextmanager
def _running_api(
    database_url: str,
    migrated_engine: Engine,
    deployment: WebDeployment = PRODUCTION,
) -> Iterator[ApiContext]:
    issuer = FakeExtensionIssuer()
    seeded = _seed_session(migrated_engine)
    application = create_app(
        _settings(database_url, deployment),
        auth_transport=httpx2.MockTransport(issuer.handle_jwks),
    )
    with TestClient(application, base_url=deployment.api_origin) as client:
        yield ApiContext(client, issuer, migrated_engine, deployment, seeded)


@pytest.fixture
def api_context(database_url: str, migrated_engine: Engine) -> Iterator[ApiContext]:
    with _running_api(database_url, migrated_engine) as context:
        yield context


def _cookie_header(context: ApiContext, value: str | None = None) -> str:
    secret = context.seeded.session_secret if value is None else value
    return f"{context.deployment.session_cookie}={secret}"


def _web_headers(
    context: ApiContext,
    *,
    csrf: str | None = None,
    origin: str | None = None,
    fetch_site: str | None = "same-site",
) -> dict[str, str]:
    headers = {
        "Cookie": _cookie_header(context),
        "Origin": context.deployment.web_origin if origin is None else origin,
        "X-CSRF-Token": context.seeded.csrf_token if csrf is None else csrf,
    }
    if fetch_site is not None:
        headers["Sec-Fetch-Site"] = fetch_site
    return headers


def _snapshot(context: ApiContext) -> SessionSnapshot:
    with Session(context.engine) as database:
        record = database.get(WebSessionRecord, context.seeded.session_id)
        assert record is not None
        return SessionSnapshot(
            record.last_used_at,
            record.idle_expires_at,
            record.absolute_expires_at,
            record.revoked_at,
        )


def _display_name(context: ApiContext) -> str | None:
    with Session(context.engine) as database:
        return database.scalar(
            select(UserRecord.display_name).where(UserRecord.id == context.seeded.user_id)
        )


def _set_session_case(context: ApiContext, case: str) -> dict[str, str]:
    if case == "missing":
        return {}
    if case == "malformed":
        return {"Cookie": _cookie_header(context, "not-an-opaque-secret")}
    if case == "unknown":
        return {"Cookie": _cookie_header(context, _opaque(0x7F))}

    with Session(context.engine) as database:
        record = database.get(WebSessionRecord, context.seeded.session_id)
        assert record is not None
        if case == "expired":
            now = datetime.now(UTC)
            record.created_at = now - timedelta(days=4)
            record.last_used_at = now - timedelta(days=3)
            record.idle_expires_at = now - timedelta(days=2)
            record.absolute_expires_at = now - timedelta(days=1)
        elif case == "revoked":
            record.revoked_at = datetime.now(UTC)
        else:
            raise AssertionError(f"unknown session case: {case}")
        database.commit()
    return {"Cookie": _cookie_header(context)}


def _assert_error(response: httpx2.Response, status: int, code: str) -> None:
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def _assert_no_cookie_change(response: httpx2.Response) -> None:
    assert response.headers.get_list("set-cookie") == []


def _assert_session_cookie_deleted(response: httpx2.Response, deployment: WebDeployment) -> None:
    raw_headers = response.headers.get_list("set-cookie")
    assert len(raw_headers) == 1
    parsed = SimpleCookie()
    parsed.load(raw_headers[0])
    assert set(parsed) == {deployment.session_cookie}
    cookie = parsed[deployment.session_cookie]
    assert cookie.value == ""
    assert cookie["max-age"] == "0"
    assert cookie["path"] == "/"
    assert cookie["samesite"].lower() == "lax"
    assert bool(cookie["httponly"])
    assert bool(cookie["secure"]) is deployment.secure
    assert cookie["domain"] == ""


def test_me_returns_the_same_safe_user_for_web_cookie_and_extension_bearer(
    api_context: ApiContext,
) -> None:
    web = api_context.client.get(
        "/api/v1/auth/me",
        headers={"Cookie": _cookie_header(api_context)},
    )
    extension = api_context.client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {api_context.issuer.token()}"},
    )

    assert web.status_code == 200
    assert extension.status_code == 200
    assert web.json() == extension.json()
    assert set(web.json()) == {"data"}
    assert set(web.json()["data"]) == {
        "id",
        "email",
        "displayName",
        "locale",
        "timeZone",
        "createdAt",
        "updatedAt",
    }
    serialized = web.text
    for private_value in (
        ISSUER,
        "auth0|same-user",
        api_context.seeded.session_secret,
        api_context.seeded.csrf_token,
        str(api_context.seeded.session_id),
    ):
        assert private_value not in serialized


@pytest.mark.parametrize("case", ["missing", "malformed", "unknown", "expired", "revoked"])
def test_me_rejects_every_invalid_web_session_with_one_external_semantic(
    api_context: ApiContext,
    case: str,
) -> None:
    response = api_context.client.get(
        "/api/v1/auth/me",
        headers=_set_session_case(api_context, case),
    )

    _assert_error(response, 401, "AUTHENTICATION_REQUIRED")
    assert api_context.seeded.session_secret not in response.text


def test_me_rejects_cookie_and_bearer_as_ambiguous(api_context: ApiContext) -> None:
    response = api_context.client.get(
        "/api/v1/auth/me",
        headers={
            "Cookie": _cookie_header(api_context),
            "Authorization": f"Bearer {api_context.issuer.token()}",
        },
    )

    _assert_error(response, 400, "AMBIGUOUS_CREDENTIALS")
    assert api_context.issuer.requests == []


def test_me_rejects_query_credentials_even_with_a_valid_web_cookie(
    api_context: ApiContext,
) -> None:
    before = _snapshot(api_context)

    response = api_context.client.get(
        "/api/v1/auth/me",
        params={"access_token": "must-not-be-accepted"},
        headers={"Cookie": _cookie_header(api_context)},
    )

    _assert_error(response, 400, "BAD_REQUEST")
    assert "must-not-be-accepted" not in response.text
    assert _snapshot(api_context) == before


@pytest.mark.parametrize("deployment", [PRODUCTION, LOOPBACK_DEVELOPMENT])
def test_me_accepts_only_the_cookie_name_for_the_current_deployment(
    database_url: str,
    migrated_engine: Engine,
    deployment: WebDeployment,
) -> None:
    with _running_api(database_url, migrated_engine, deployment) as context:
        accepted = context.client.get(
            "/api/v1/auth/me",
            headers={"Cookie": _cookie_header(context)},
        )
        wrong_environment = context.client.get(
            "/api/v1/auth/me",
            headers={
                "Cookie": (f"{deployment.other_session_cookie}={context.seeded.session_secret}")
            },
        )
        both_reserved = context.client.get(
            "/api/v1/auth/me",
            headers={
                "Cookie": (
                    f"{deployment.session_cookie}={context.seeded.session_secret}; "
                    f"{deployment.other_session_cookie}={context.seeded.session_secret}"
                )
            },
        )

    assert accepted.status_code == 200
    _assert_error(wrong_environment, 401, "AUTHENTICATION_REQUIRED")
    _assert_error(both_reserved, 400, "AMBIGUOUS_CREDENTIALS")


def test_successful_web_me_slides_idle_expiry(api_context: ApiContext) -> None:
    before = _snapshot(api_context)

    response = api_context.client.get(
        "/api/v1/auth/me",
        headers={"Cookie": _cookie_header(api_context)},
    )

    after = _snapshot(api_context)
    assert response.status_code == 200
    assert after.last_used_at > before.last_used_at
    assert after.idle_expires_at > before.idle_expires_at
    assert after.idle_expires_at <= after.absolute_expires_at


def test_web_me_idle_slide_is_capped_by_absolute_expiry(api_context: ApiContext) -> None:
    now = datetime.now(UTC)
    with Session(api_context.engine) as database:
        record = database.get(WebSessionRecord, api_context.seeded.session_id)
        assert record is not None
        record.created_at = now - timedelta(hours=2)
        record.last_used_at = now - timedelta(hours=1)
        record.idle_expires_at = now + timedelta(minutes=1)
        record.absolute_expires_at = now + timedelta(minutes=5)
        database.commit()

    response = api_context.client.get(
        "/api/v1/auth/me",
        headers={"Cookie": _cookie_header(api_context)},
    )

    refreshed = _snapshot(api_context)
    assert response.status_code == 200
    assert refreshed.idle_expires_at == refreshed.absolute_expires_at


def test_csrf_returns_only_the_session_bound_token_without_caching(
    api_context: ApiContext,
) -> None:
    response = api_context.client.get(
        "/api/v1/auth/csrf",
        headers={"Cookie": _cookie_header(api_context)},
    )

    assert response.status_code == 200
    assert response.json() == {"data": {"csrfToken": api_context.seeded.csrf_token}}
    assert response.headers["Cache-Control"] == "no-store"
    assert api_context.seeded.session_secret not in response.text


@pytest.mark.parametrize("case", ["missing", "malformed", "unknown", "expired", "revoked"])
def test_csrf_rejects_every_invalid_web_session(
    api_context: ApiContext,
    case: str,
) -> None:
    response = api_context.client.get(
        "/api/v1/auth/csrf",
        headers=_set_session_case(api_context, case),
    )

    _assert_error(response, 401, "AUTHENTICATION_REQUIRED")


def test_csrf_rejects_bearer_without_validating_it(api_context: ApiContext) -> None:
    response = api_context.client.get(
        "/api/v1/auth/csrf",
        headers={"Authorization": f"Bearer {api_context.issuer.token()}"},
    )

    _assert_error(response, 401, "AUTHENTICATION_REQUIRED")
    assert api_context.issuer.requests == []


def test_csrf_rejects_mixed_credentials(api_context: ApiContext) -> None:
    response = api_context.client.get(
        "/api/v1/auth/csrf",
        headers={
            "Cookie": _cookie_header(api_context),
            "Authorization": f"Bearer {api_context.issuer.token()}",
        },
    )

    _assert_error(response, 400, "AMBIGUOUS_CREDENTIALS")
    assert api_context.issuer.requests == []


@pytest.mark.parametrize("fetch_site", ["same-origin", "same-site"])
def test_patch_accepts_a_legitimate_cookie_mutation(
    api_context: ApiContext,
    fetch_site: str,
) -> None:
    response = api_context.client.patch(
        "/api/v1/auth/me",
        headers=_web_headers(api_context, fetch_site=fetch_site),
        json={"displayName": "Cookie Updated"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["displayName"] == "Cookie Updated"
    assert _display_name(api_context) == "Cookie Updated"


def test_patch_accepts_bearer_without_browser_csrf_headers(api_context: ApiContext) -> None:
    response = api_context.client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {api_context.issuer.token()}"},
        json={"displayName": "Extension Updated"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["displayName"] == "Extension Updated"


@pytest.mark.parametrize(
    ("origin", "fetch_site", "csrf"),
    [
        ("", "same-site", None),
        ("https://attacker.example.invalid", "same-site", None),
        (None, None, None),
        (None, "cross-site", None),
        (None, "none", None),
        (None, "same-site", ""),
        (None, "same-site", "wrong-csrf-token"),
    ],
    ids=[
        "missing-origin",
        "wrong-origin",
        "missing-fetch-metadata",
        "cross-site-fetch",
        "none-fetch",
        "missing-csrf",
        "wrong-csrf",
    ],
)
def test_patch_rejects_invalid_browser_security_gates_without_writes_or_session_touch(
    api_context: ApiContext,
    origin: str | None,
    fetch_site: str | None,
    csrf: str | None,
) -> None:
    headers = _web_headers(api_context)
    if origin == "":
        headers.pop("Origin")
    elif origin is not None:
        headers["Origin"] = origin
    if fetch_site is None:
        headers.pop("Sec-Fetch-Site")
    else:
        headers["Sec-Fetch-Site"] = fetch_site
    if csrf == "":
        headers.pop("X-CSRF-Token")
    elif csrf is not None:
        headers["X-CSRF-Token"] = csrf
    before = _snapshot(api_context)

    response = api_context.client.patch(
        "/api/v1/auth/me",
        headers=headers,
        json={"displayName": "Must Not Persist"},
    )

    _assert_error(response, 403, "FORBIDDEN")
    assert _display_name(api_context) == "Existing User"
    assert _snapshot(api_context) == before


def test_patch_rejects_mixed_credentials_before_authentication(api_context: ApiContext) -> None:
    before = _snapshot(api_context)
    headers = _web_headers(api_context)
    headers["Authorization"] = f"Bearer {api_context.issuer.token()}"

    response = api_context.client.patch(
        "/api/v1/auth/me",
        headers=headers,
        json={"displayName": "Must Not Persist"},
    )

    _assert_error(response, 400, "AMBIGUOUS_CREDENTIALS")
    assert api_context.issuer.requests == []
    assert _display_name(api_context) == "Existing User"
    assert _snapshot(api_context) == before


@pytest.mark.parametrize(
    ("origin", "fetch_site"),
    [
        (None, "same-site"),
        ("https://attacker.example.invalid", "same-site"),
        (PRODUCTION.web_origin, None),
        (PRODUCTION.web_origin, "cross-site"),
        (PRODUCTION.web_origin, "none"),
    ],
    ids=[
        "missing-origin",
        "wrong-origin",
        "missing-fetch-metadata",
        "cross-site-fetch",
        "none-fetch",
    ],
)
def test_logout_checks_origin_and_fetch_before_body_credentials_or_session(
    api_context: ApiContext,
    origin: str | None,
    fetch_site: str | None,
) -> None:
    headers = {
        "Cookie": _cookie_header(api_context),
        "Authorization": f"Bearer {api_context.issuer.token()}",
        "X-CSRF-Token": "wrong-token",
    }
    if origin is not None:
        headers["Origin"] = origin
    if fetch_site is not None:
        headers["Sec-Fetch-Site"] = fetch_site
    before = _snapshot(api_context)

    response = api_context.client.post(
        "/api/v1/auth/logout",
        headers=headers,
        json={"unexpected": True},
    )

    _assert_error(response, 403, "FORBIDDEN")
    _assert_no_cookie_change(response)
    assert api_context.issuer.requests == []
    assert _snapshot(api_context) == before


def test_logout_rejects_bearer_only_without_validating_jwt(api_context: ApiContext) -> None:
    response = api_context.client.post(
        "/api/v1/auth/logout",
        headers={
            "Origin": api_context.deployment.web_origin,
            "Sec-Fetch-Site": "same-site",
            "Authorization": f"Bearer {api_context.issuer.token()}",
        },
    )

    _assert_error(response, 400, "BAD_REQUEST")
    _assert_no_cookie_change(response)
    assert api_context.issuer.requests == []


def test_logout_rejects_query_credentials_without_clearing_or_revoking(
    api_context: ApiContext,
) -> None:
    before = _snapshot(api_context)

    response = api_context.client.post(
        "/api/v1/auth/logout",
        params={"access_token": "must-not-be-accepted"},
        headers={
            "Origin": api_context.deployment.web_origin,
            "Sec-Fetch-Site": "same-site",
        },
    )

    _assert_error(response, 400, "BAD_REQUEST")
    _assert_no_cookie_change(response)
    assert "must-not-be-accepted" not in response.text
    assert _snapshot(api_context) == before


def test_logout_rejects_mixed_credentials_without_revoking(api_context: ApiContext) -> None:
    before = _snapshot(api_context)
    headers = _web_headers(api_context)
    headers["Authorization"] = f"Bearer {api_context.issuer.token()}"

    response = api_context.client.post("/api/v1/auth/logout", headers=headers)

    _assert_error(response, 400, "AMBIGUOUS_CREDENTIALS")
    _assert_no_cookie_change(response)
    assert api_context.issuer.requests == []
    assert _snapshot(api_context) == before


@pytest.mark.parametrize("csrf", ["", "wrong-csrf-token"], ids=["missing", "wrong"])
def test_logout_keeps_a_valid_session_when_csrf_fails(
    api_context: ApiContext,
    csrf: str,
) -> None:
    headers = _web_headers(api_context)
    if not csrf:
        headers.pop("X-CSRF-Token")
    else:
        headers["X-CSRF-Token"] = csrf
    before = _snapshot(api_context)

    response = api_context.client.post("/api/v1/auth/logout", headers=headers)

    _assert_error(response, 403, "FORBIDDEN")
    _assert_no_cookie_change(response)
    assert _snapshot(api_context) == before


@pytest.mark.parametrize("fetch_site", ["same-origin", "same-site"])
def test_logout_revokes_the_session_clears_cookie_and_blocks_replay(
    api_context: ApiContext,
    fetch_site: str,
) -> None:
    response = api_context.client.post(
        "/api/v1/auth/logout",
        headers=_web_headers(api_context, fetch_site=fetch_site),
    )

    assert response.status_code == 204
    assert response.content == b""
    assert _snapshot(api_context).revoked_at is not None
    _assert_session_cookie_deleted(response, api_context.deployment)
    replay = api_context.client.get(
        "/api/v1/auth/me",
        headers={"Cookie": _cookie_header(api_context)},
    )
    _assert_error(replay, 401, "AUTHENTICATION_REQUIRED")


@pytest.mark.parametrize("case", ["missing", "malformed", "unknown", "expired", "revoked"])
def test_logout_is_idempotent_for_every_invalid_session(
    api_context: ApiContext,
    case: str,
) -> None:
    headers = {
        "Origin": api_context.deployment.web_origin,
        "Sec-Fetch-Site": "same-site",
        **_set_session_case(api_context, case),
    }

    response = api_context.client.post("/api/v1/auth/logout", headers=headers)

    assert response.status_code == 204
    assert response.content == b""
    _assert_session_cookie_deleted(response, api_context.deployment)


@pytest.mark.parametrize("deployment", [PRODUCTION, LOOPBACK_DEVELOPMENT])
def test_logout_ignores_wrong_environment_cookie_and_clears_only_current_cookie(
    database_url: str,
    migrated_engine: Engine,
    deployment: WebDeployment,
) -> None:
    with _running_api(database_url, migrated_engine, deployment) as context:
        response = context.client.post(
            "/api/v1/auth/logout",
            headers={
                "Origin": deployment.web_origin,
                "Sec-Fetch-Site": "same-site",
                "Cookie": (f"{deployment.other_session_cookie}={context.seeded.session_secret}"),
            },
        )

    assert response.status_code == 204
    _assert_session_cookie_deleted(response, deployment)


def test_logout_store_outage_does_not_clear_or_revoke_session(
    api_context: ApiContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_enter(self: SqlAlchemyWebSessionUnitOfWork) -> None:
        raise WebSessionPersistenceError

    before = _snapshot(api_context)
    monkeypatch.setattr(SqlAlchemyWebSessionUnitOfWork, "__enter__", fail_enter)

    response = api_context.client.post(
        "/api/v1/auth/logout",
        headers=_web_headers(api_context),
    )

    assert response.status_code == 503
    _assert_no_cookie_change(response)
    assert _snapshot(api_context) == before


def test_logout_rejects_nonempty_body_without_revoking_or_clearing_cookie(
    api_context: ApiContext,
) -> None:
    before = _snapshot(api_context)

    response = api_context.client.post(
        "/api/v1/auth/logout",
        headers=_web_headers(api_context),
        json={"unexpected": True},
    )

    _assert_error(response, 422, "VALIDATION_ERROR")
    _assert_no_cookie_change(response)
    assert _snapshot(api_context) == before
