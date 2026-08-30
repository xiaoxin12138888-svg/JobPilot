from __future__ import annotations

import base64
import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from jobpilot_api.config import ApiSettings, AuthSettings
from jobpilot_api.infrastructure.database.models import (
    IdentityRecord,
    LoginTransactionRecord,
    UserRecord,
    WebSessionRecord,
)
from jobpilot_api.main import create_app

ISSUER = "https://tenant.example.invalid/"
JWKS_URL = "https://tenant.example.invalid/.well-known/jwks.json"
AUTHORIZE_URL = "https://tenant.example.invalid/authorize"
TOKEN_URL = "https://tenant.example.invalid/oauth/token"
AUDIENCE = "https://api.jobpilot.example.invalid"
EXTENSION_CLIENT_ID = "extension-client-id"
WEB_CLIENT_ID = "web-client-id"
WEB_CLIENT_SECRET = "web-client-secret-private-value"
EMAIL_CLAIM = "https://jobpilot.example.invalid/claims/email"
EMAIL_VERIFIED_CLAIM = "https://jobpilot.example.invalid/claims/email_verified"
CALLBACK_PATH = "/api/v1/auth/web/callback"
AUTHORIZE_PATH = "/api/v1/auth/web/authorize"
AUTHORIZATION_CODE = "provider-code-private-value"
PROVIDER_ERROR_DETAIL = "provider-private-error-detail"


@dataclass(frozen=True, slots=True)
class WebDeployment:
    environment: str
    web_origin: str
    api_origin: str
    transaction_cookie: str
    session_cookie: str
    secure: bool

    @property
    def callback_url(self) -> str:
        return f"{self.api_origin}{CALLBACK_PATH}"


PRODUCTION = WebDeployment(
    environment="production",
    web_origin="https://jobpilot.example.invalid",
    api_origin="https://jobpilot.example.invalid",
    transaction_cookie="__Host-jobpilot_login_tx",
    session_cookie="__Host-jobpilot_session",
    secure=True,
)
LOOPBACK_DEVELOPMENT = WebDeployment(
    environment="development",
    web_origin="http://localhost:5173",
    api_origin="http://localhost:8000",
    transaction_cookie="jobpilot_dev_login_tx",
    session_cookie="jobpilot_dev_session",
    secure=False,
)


def _digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("ascii")).digest()


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _fixed_opaque(byte: int) -> str:
    return _base64url(bytes([byte]) * 32)


def _is_opaque_256_bit(value: str) -> bool:
    try:
        encoded = value.encode("ascii")
        decoded = base64.b64decode(
            encoded + b"=" * (-len(encoded) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (UnicodeEncodeError, ValueError):
        return False
    return len(decoded) == 32 and _base64url(decoded) == value


class FakeAuth0:
    def __init__(self) -> None:
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_jwk = RSAAlgorithm.to_jwk(self._private_key.public_key(), as_dict=True)
        assert isinstance(public_jwk, dict)
        public_jwk.update({"kid": "key-1", "alg": "RS256", "use": "sig"})
        self._jwks = {"keys": [public_jwk]}
        self.requests: list[httpx2.Request] = []
        self.next_nonce: str | None = None
        self.subject = "auth0|web-subject"
        self.email = "Person@Example.COM"
        self.email_verified = True
        self.token_status = 200
        self.raw_id_tokens: list[str] = []
        self.raw_access_tokens: list[str] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        request_url = str(request.url)
        if request.method == "GET" and request_url == JWKS_URL:
            return httpx2.Response(200, json=self._jwks)
        if request.method == "POST" and request_url == TOKEN_URL:
            if self.token_status != 200:
                return httpx2.Response(
                    self.token_status,
                    json={
                        "error": "provider_failure",
                        "error_description": PROVIDER_ERROR_DETAIL,
                    },
                )
            if self.next_nonce is None:
                pytest.fail("The token endpoint was called without an authorization nonce")
            raw_id_token = self._id_token(self.next_nonce)
            raw_access_token = f"provider-access-token-{len(self.raw_access_tokens) + 1}"
            self.next_nonce = None
            self.raw_id_tokens.append(raw_id_token)
            self.raw_access_tokens.append(raw_access_token)
            return httpx2.Response(
                200,
                json={
                    "access_token": raw_access_token,
                    "id_token": raw_id_token,
                    "token_type": "Bearer",
                    "expires_in": 300,
                },
            )
        pytest.fail(f"Unexpected provider request: {request.method} {request_url}")

    def _id_token(self, nonce: str) -> str:
        now = int(datetime.now(UTC).timestamp())
        return jwt.encode(
            {
                "iss": ISSUER,
                "aud": WEB_CLIENT_ID,
                "exp": now + 300,
                "iat": now - 1,
                "nbf": now - 1,
                "auth_time": now - 30,
                "sub": self.subject,
                "azp": WEB_CLIENT_ID,
                "nonce": nonce,
                "email": self.email,
                "email_verified": self.email_verified,
            },
            self._private_key,
            algorithm="RS256",
            headers={"typ": "JWT", "kid": "key-1"},
        )


@dataclass(slots=True)
class ApiContext:
    client: TestClient
    provider: FakeAuth0
    engine: Engine
    deployment: WebDeployment


@dataclass(frozen=True, slots=True)
class StartedLogin:
    state: str
    nonce: str
    browser_handle: str


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
            web_client_secret=WEB_CLIENT_SECRET,
            web_origin=deployment.web_origin,
            web_callback_url=deployment.callback_url,
            access_token_email_claim=EMAIL_CLAIM,
            access_token_email_verified_claim=EMAIL_VERIFIED_CLAIM,
            web_session_idle_seconds=604_800,
            web_session_absolute_seconds=2_592_000,
        ),
        database_url=database_url,
    )


@contextmanager
def _running_api(
    database_url: str,
    migrated_engine: Engine,
    deployment: WebDeployment = PRODUCTION,
) -> Iterator[ApiContext]:
    provider = FakeAuth0()
    application = create_app(
        _settings(database_url, deployment),
        auth_transport=httpx2.MockTransport(provider),
    )
    with TestClient(application, base_url=deployment.api_origin) as client:
        yield ApiContext(client, provider, migrated_engine, deployment)


def _cookie_header(response: httpx2.Response, cookie_name: str) -> str:
    matches = [
        header
        for header in response.headers.get_list("set-cookie")
        if header.startswith(f"{cookie_name}=")
    ]
    assert len(matches) == 1
    return matches[0]


def _cookie_value(cookie_header: str) -> str:
    return cookie_header.split(";", 1)[0].split("=", 1)[1].strip('"')


def _assert_cookie_attributes(
    cookie_header: str,
    *,
    secure: bool,
    max_age: int | None = None,
) -> None:
    normalized = cookie_header.lower()
    assert "httponly" in normalized
    assert "samesite=lax" in normalized
    assert "path=/" in normalized
    assert ("secure" in normalized) is secure
    assert "domain=" not in normalized
    if max_age is not None:
        assert f"max-age={max_age}" in normalized


def _assert_transaction_cookie_cleared(
    response: httpx2.Response,
    deployment: WebDeployment,
) -> None:
    cookie_header = _cookie_header(response, deployment.transaction_cookie)
    _assert_cookie_attributes(cookie_header, secure=deployment.secure)
    assert "max-age=0" in cookie_header.lower()


def _authorize_query(location: str) -> tuple[list[tuple[str, str]], dict[str, str]]:
    parsed = urlsplit(location)
    assert urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", "")) == AUTHORIZE_URL
    pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    query = dict(pairs)
    assert len(query) == len(pairs)
    assert parsed.fragment == ""
    return pairs, query


def _begin_login(context: ApiContext, *, intent: str = "login") -> StartedLogin:
    response = context.client.get(
        AUTHORIZE_PATH,
        params={"intent": intent, "returnTo": "/"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    _, query = _authorize_query(response.headers["location"])
    browser_handle = _cookie_value(_cookie_header(response, context.deployment.transaction_cookie))
    return StartedLogin(
        state=query["state"],
        nonce=query["nonce"],
        browser_handle=browser_handle,
    )


def _complete_login(
    context: ApiContext,
    started: StartedLogin,
    *,
    code: str = AUTHORIZATION_CODE,
) -> httpx2.Response:
    context.provider.next_nonce = started.nonce
    return context.client.get(
        CALLBACK_PATH,
        params={"code": code, "state": started.state},
        follow_redirects=False,
    )


def _record_counts(engine: Engine) -> tuple[int, int, int, int]:
    with Session(engine) as session:
        return (
            session.scalar(select(func.count()).select_from(UserRecord)) or 0,
            session.scalar(select(func.count()).select_from(IdentityRecord)) or 0,
            session.scalar(select(func.count()).select_from(WebSessionRecord)) or 0,
            session.scalar(select(func.count()).select_from(LoginTransactionRecord)) or 0,
        )


def _seed_identity(
    engine: Engine,
    *,
    subject: str,
    account_status: str = "active",
) -> None:
    now = datetime.now(UTC)
    with Session(engine) as session:
        user = UserRecord(
            email="person@example.com",
            account_status=account_status,
            deletion_requested_at=now if account_status == "deletion_pending" else None,
        )
        session.add(user)
        session.flush()
        session.add(
            IdentityRecord(
                user_id=user.id,
                issuer=ISSUER,
                subject=subject,
            )
        )
        session.commit()


def _persistence_snapshot(engine: Engine) -> str:
    records: list[tuple[str, tuple[object, ...]]] = []
    with Session(engine) as session:
        for model in (UserRecord, IdentityRecord, WebSessionRecord, LoginTransactionRecord):
            for record in session.scalars(select(model)).all():
                values = tuple(getattr(record, column.name) for column in model.__table__.columns)
                records.append((model.__name__, values))
    return repr(records)


@pytest.mark.parametrize("deployment", [PRODUCTION, LOOPBACK_DEVELOPMENT], ids=["https", "dev"])
@pytest.mark.parametrize(
    ("intent", "hint_name", "hint_value"),
    [("login", "prompt", "login"), ("signup", "screen_hint", "signup")],
)
def test_web_authorize_creates_a_browser_bound_pkce_transaction(
    database_url: str,
    migrated_engine: Engine,
    deployment: WebDeployment,
    intent: str,
    hint_name: str,
    hint_value: str,
) -> None:
    with _running_api(database_url, migrated_engine, deployment) as context:
        response = context.client.get(
            AUTHORIZE_PATH,
            params={"intent": intent, "returnTo": "/"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers["Referrer-Policy"] == "no-referrer"
        pairs, query = _authorize_query(response.headers["location"])
        expected_query = {
            "response_type": "code",
            "client_id": WEB_CLIENT_ID,
            "redirect_uri": deployment.callback_url,
            "scope": "openid profile email",
            "state": query["state"],
            "nonce": query["nonce"],
            "code_challenge": query["code_challenge"],
            "code_challenge_method": "S256",
            hint_name: hint_value,
        }
        assert dict(pairs) == expected_query
        assert len(pairs) == len(expected_query)
        assert _is_opaque_256_bit(query["state"])
        assert _is_opaque_256_bit(query["nonce"])
        assert _is_opaque_256_bit(query["code_challenge"])
        assert WEB_CLIENT_SECRET not in response.headers["location"]
        assert "offline_access" not in response.headers["location"]

        transaction_cookie = _cookie_header(response, deployment.transaction_cookie)
        _assert_cookie_attributes(transaction_cookie, secure=deployment.secure, max_age=600)
        browser_handle = _cookie_value(transaction_cookie)
        assert _is_opaque_256_bit(browser_handle)

        with Session(migrated_engine) as session:
            transaction = session.scalars(select(LoginTransactionRecord)).one()
            assert transaction.browser_handle_hash == _digest(browser_handle)
            assert transaction.state_hash == _digest(query["state"])
            assert transaction.nonce_hash == _digest(query["nonce"])
            assert transaction.intent == intent
            assert transaction.return_to == "/"
            assert (transaction.expires_at - transaction.created_at).total_seconds() == 600
            assert _base64url(_digest(transaction.pkce_verifier)) == query["code_challenge"]
        assert context.provider.requests == []


def test_web_authorize_defaults_the_optional_return_path_to_root(
    database_url: str,
    migrated_engine: Engine,
) -> None:
    with _running_api(database_url, migrated_engine) as context:
        response = context.client.get(
            AUTHORIZE_PATH,
            params={"intent": "login"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        with Session(migrated_engine) as session:
            transaction = session.scalars(select(LoginTransactionRecord)).one()
            assert transaction.return_to == "/"


@pytest.mark.parametrize(
    "query",
    [
        {"returnTo": "/"},
        {"intent": "extension", "returnTo": "/"},
        {"intent": "login", "returnTo": "https://attacker.invalid/steal"},
        {"intent": "login", "returnTo": "//attacker.invalid/steal"},
        {"intent": "login", "returnTo": "/not-allowlisted"},
    ],
    ids=[
        "missing-intent",
        "invalid-intent",
        "absolute-url",
        "protocol-relative-url",
        "unknown-path",
    ],
)
def test_web_authorize_rejects_invalid_intent_and_open_redirect_inputs_without_side_effects(
    database_url: str,
    migrated_engine: Engine,
    query: dict[str, str],
) -> None:
    with _running_api(database_url, migrated_engine) as context:
        response = context.client.get(
            AUTHORIZE_PATH,
            params=query,
            follow_redirects=False,
        )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "BAD_REQUEST"
        assert "set-cookie" not in response.headers
        assert _record_counts(migrated_engine) == (0, 0, 0, 0)
        assert context.provider.requests == []


@pytest.mark.parametrize(
    "query",
    [
        [("intent", "login"), ("intent", "signup")],
        [("intent", "login"), ("returnTo", "/"), ("returnTo", "/")],
    ],
    ids=["duplicate-intent", "duplicate-return-to"],
)
def test_web_authorize_rejects_duplicate_security_parameters_without_side_effects(
    database_url: str,
    migrated_engine: Engine,
    query: list[tuple[str, str]],
) -> None:
    with _running_api(database_url, migrated_engine) as context:
        response = context.client.get(
            AUTHORIZE_PATH,
            params=query,
            follow_redirects=False,
        )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "BAD_REQUEST"
        assert "set-cookie" not in response.headers
        assert _record_counts(migrated_engine) == (0, 0, 0, 0)
        assert context.provider.requests == []


def test_web_authorize_rate_limit_is_bounded_and_has_retry_after(
    database_url: str,
    migrated_engine: Engine,
) -> None:
    with _running_api(database_url, migrated_engine) as context:
        responses = [context.client.get(AUTHORIZE_PATH, follow_redirects=False) for _ in range(11)]

        assert [response.status_code for response in responses[:10]] == [400] * 10
        limited = responses[-1]
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "RATE_LIMITED"
        assert 1 <= int(limited.headers["Retry-After"]) <= 60
        assert "set-cookie" not in limited.headers
        assert _record_counts(migrated_engine) == (0, 0, 0, 0)
        assert context.provider.requests == []


@pytest.mark.parametrize("deployment", [PRODUCTION, LOOPBACK_DEVELOPMENT], ids=["https", "dev"])
def test_web_callback_creates_an_opaque_session_and_discards_provider_tokens(
    database_url: str,
    migrated_engine: Engine,
    deployment: WebDeployment,
) -> None:
    with _running_api(database_url, migrated_engine, deployment) as context:
        started = _begin_login(context)

        response = _complete_login(context, started)

        assert response.status_code == 303
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert response.headers["location"] == f"{deployment.web_origin}/"
        _assert_transaction_cookie_cleared(response, deployment)
        session_cookie = _cookie_header(response, deployment.session_cookie)
        _assert_cookie_attributes(
            session_cookie,
            secure=deployment.secure,
            max_age=2_592_000,
        )
        session_secret = _cookie_value(session_cookie)
        assert _is_opaque_256_bit(session_secret)
        assert session_secret.count(".") != 2
        assert session_secret != started.browser_handle
        assert _record_counts(migrated_engine) == (1, 1, 1, 0)

        with Session(migrated_engine) as session:
            user = session.scalars(select(UserRecord)).one()
            identity = session.scalars(select(IdentityRecord)).one()
            stored_session = session.scalars(select(WebSessionRecord)).one()
            assert user.email == "person@example.com"
            assert identity.user_id == user.id
            assert identity.issuer == ISSUER
            assert identity.subject == context.provider.subject
            assert stored_session.user_id == user.id
            assert stored_session.identity_id == identity.id
            assert stored_session.session_token_hash == _digest(session_secret)

        assert context.provider.raw_id_tokens
        assert context.provider.raw_access_tokens
        persisted = _persistence_snapshot(migrated_engine)
        assert session_secret not in persisted
        for provider_token in (
            *context.provider.raw_id_tokens,
            *context.provider.raw_access_tokens,
        ):
            assert provider_token not in persisted
            rendered_response = f"{response.headers!r}\n{response.text}"
            assert provider_token not in rendered_response


@pytest.mark.parametrize("deployment", [PRODUCTION, LOOPBACK_DEVELOPMENT], ids=["https", "dev"])
@pytest.mark.parametrize(
    "failure",
    ["missing-state", "missing-cookie", "wrong-state", "provider-error"],
)
def test_web_callback_failures_share_one_sanitized_redirect_and_consume_transactions(
    database_url: str,
    migrated_engine: Engine,
    deployment: WebDeployment,
    failure: str,
) -> None:
    with _running_api(database_url, migrated_engine, deployment) as context:
        started = _begin_login(context)
        params = {"code": AUTHORIZATION_CODE, "state": started.state}
        if failure == "missing-state":
            del params["state"]
        elif failure == "missing-cookie":
            context.client.cookies.clear()
        elif failure == "wrong-state":
            params["state"] = _fixed_opaque(255)
            assert params["state"] != started.state
        else:
            params = {
                "error": "access_denied",
                "error_description": PROVIDER_ERROR_DETAIL,
                "state": started.state,
            }

        response = context.client.get(
            CALLBACK_PATH,
            params=params,
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert response.headers["location"] == f"{deployment.web_origin}/auth/error"
        _assert_transaction_cookie_cleared(response, deployment)
        assert deployment.session_cookie not in response.headers.get("set-cookie", "")
        assert _record_counts(migrated_engine) == (0, 0, 0, 0)
        assert context.provider.requests == []
        rendered = f"{response.headers['location']}\n{response.text}"
        assert "access_denied" not in rendered
        assert PROVIDER_ERROR_DETAIL not in rendered
        assert AUTHORIZATION_CODE not in rendered


def test_web_callback_expired_transaction_is_consumed_and_redirected_safely(
    database_url: str,
    migrated_engine: Engine,
) -> None:
    with _running_api(database_url, migrated_engine) as context:
        started = _begin_login(context)
        with Session(migrated_engine) as session:
            transaction = session.scalars(select(LoginTransactionRecord)).one()
            transaction.expires_at = datetime.now(UTC)
            session.commit()

        response = context.client.get(
            CALLBACK_PATH,
            params={"code": AUTHORIZATION_CODE, "state": started.state},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"{PRODUCTION.web_origin}/auth/error"
        _assert_transaction_cookie_cleared(response, PRODUCTION)
        assert _record_counts(migrated_engine) == (0, 0, 0, 0)
        assert context.provider.requests == []


@pytest.mark.parametrize("duplicate", ["code", "state"])
def test_web_callback_rejects_duplicate_security_parameters_and_consumes_transaction(
    database_url: str,
    migrated_engine: Engine,
    duplicate: str,
) -> None:
    with _running_api(database_url, migrated_engine) as context:
        started = _begin_login(context)
        params = [("code", AUTHORIZATION_CODE), ("state", started.state)]
        params.append((duplicate, "attacker-controlled-duplicate"))

        response = context.client.get(
            CALLBACK_PATH,
            params=params,
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"{PRODUCTION.web_origin}/auth/error"
        _assert_transaction_cookie_cleared(response, PRODUCTION)
        assert PRODUCTION.session_cookie not in response.headers.get("set-cookie", "")
        assert _record_counts(migrated_engine) == (0, 0, 0, 0)
        assert context.provider.requests == []
        assert "attacker-controlled-duplicate" not in response.headers["location"]


@pytest.mark.parametrize("oversized", ["cookie", "state"])
def test_web_callback_rejects_oversized_opaque_values_and_consumes_transaction(
    database_url: str,
    migrated_engine: Engine,
    oversized: str,
) -> None:
    with _running_api(database_url, migrated_engine) as context:
        started = _begin_login(context)
        params = {"code": AUTHORIZATION_CODE, "state": started.state}
        if oversized == "state":
            params["state"] = "A" * 10_000
        else:
            context.client.cookies.set(PRODUCTION.transaction_cookie, "A" * 10_000)

        response = context.client.get(
            CALLBACK_PATH,
            params=params,
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"{PRODUCTION.web_origin}/auth/error"
        _assert_transaction_cookie_cleared(response, PRODUCTION)
        assert PRODUCTION.session_cookie not in response.headers.get("set-cookie", "")
        assert _record_counts(migrated_engine) == (0, 0, 0, 0)
        assert context.provider.requests == []


@pytest.mark.parametrize(
    "failure",
    ["provider-outage", "unverified-email", "identity-conflict", "deletion-pending"],
)
def test_web_callback_post_exchange_failures_share_the_sanitized_redirect(
    database_url: str,
    migrated_engine: Engine,
    failure: str,
) -> None:
    with _running_api(database_url, migrated_engine) as context:
        if failure == "provider-outage":
            context.provider.token_status = 503
        elif failure == "unverified-email":
            context.provider.email_verified = False
        elif failure == "identity-conflict":
            _seed_identity(migrated_engine, subject="auth0|different-subject")
        else:
            _seed_identity(
                migrated_engine,
                subject=context.provider.subject,
                account_status="deletion_pending",
            )
        started = _begin_login(context)

        response = _complete_login(context, started)

        assert response.status_code == 303
        assert response.headers["location"] == f"{PRODUCTION.web_origin}/auth/error"
        _assert_transaction_cookie_cleared(response, PRODUCTION)
        assert PRODUCTION.session_cookie not in response.headers.get("set-cookie", "")
        expected_identity_rows = 1 if failure in {"identity-conflict", "deletion-pending"} else 0
        assert _record_counts(migrated_engine) == (
            expected_identity_rows,
            expected_identity_rows,
            0,
            0,
        )
        rendered = f"{response.headers!r}\n{response.text}"
        for sensitive_value in (
            AUTHORIZATION_CODE,
            PROVIDER_ERROR_DETAIL,
            *context.provider.raw_id_tokens,
            *context.provider.raw_access_tokens,
        ):
            assert sensitive_value not in rendered


def test_web_callback_replay_cannot_create_a_second_session(
    database_url: str,
    migrated_engine: Engine,
) -> None:
    with _running_api(database_url, migrated_engine) as context:
        started = _begin_login(context)
        first = _complete_login(context, started, code="first-private-provider-code")
        assert first.status_code == 303
        assert _record_counts(migrated_engine) == (1, 1, 1, 0)
        provider_request_count = len(context.provider.requests)

        replay = context.client.get(
            CALLBACK_PATH,
            params={"code": "replayed-private-provider-code", "state": started.state},
            headers={"Cookie": f"{PRODUCTION.transaction_cookie}={started.browser_handle}"},
            follow_redirects=False,
        )

        assert replay.status_code == 303
        assert replay.headers["location"] == f"{PRODUCTION.web_origin}/auth/error"
        _assert_transaction_cookie_cleared(replay, PRODUCTION)
        assert PRODUCTION.session_cookie not in replay.headers.get("set-cookie", "")
        assert _record_counts(migrated_engine) == (1, 1, 1, 0)
        assert len(context.provider.requests) == provider_request_count
        assert "replayed-private-provider-code" not in replay.headers["location"]


def test_repeated_login_reuses_the_existing_identity_and_creates_a_new_session(
    database_url: str,
    migrated_engine: Engine,
) -> None:
    with _running_api(database_url, migrated_engine) as context:
        first_started = _begin_login(context)
        first = _complete_login(context, first_started, code="first-private-provider-code")
        assert first.status_code == 303
        first_session_secret = _cookie_value(_cookie_header(first, PRODUCTION.session_cookie))
        with Session(migrated_engine) as session:
            original_user_id = session.scalars(select(UserRecord.id)).one()

        second_started = _begin_login(context)
        second = _complete_login(context, second_started, code="second-private-provider-code")

        assert second.status_code == 303
        second_session_secret = _cookie_value(_cookie_header(second, PRODUCTION.session_cookie))
        assert second_session_secret != first_session_secret
        assert _record_counts(migrated_engine) == (1, 1, 2, 0)
        with Session(migrated_engine) as session:
            assert session.scalars(select(UserRecord.id)).one() == original_user_id
            sessions = session.scalars(select(WebSessionRecord)).all()
            assert len({stored.id for stored in sessions}) == 2
            assert len({stored.session_token_hash for stored in sessions}) == 2
