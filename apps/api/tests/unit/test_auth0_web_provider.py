from __future__ import annotations

import base64
import hashlib
import traceback
from collections.abc import Iterator
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from jobpilot_api.application.web_auth_service import (
    WebProviderEmailVerificationRequiredError,
    WebProviderRejectedError,
    WebProviderUnavailableError,
)
from jobpilot_api.config import AuthSettings
from jobpilot_api.domain.identity import VerifiedProviderIdentity
from jobpilot_api.infrastructure.auth.auth0_web_provider import (
    Auth0WebProvider,
    IdentityProviderResponseError,
    InvalidIdTokenError,
    SigningKeyResolver,
)
from jobpilot_api.infrastructure.auth.jwks import IdentityProviderUnavailableError

ISSUER = "https://tenant.example.invalid/"
JWKS_URL = "https://tenant.example.invalid/.well-known/jwks.json"
AUTHORIZE_URL = "https://tenant.example.invalid/authorize"
TOKEN_URL = "https://tenant.example.invalid/oauth/token"
AUDIENCE = "https://api.jobpilot.example.invalid"
EXTENSION_CLIENT_ID = "extension-client-id"
WEB_CLIENT_ID = "web-client-id"
WEB_CLIENT_SECRET = "web-client-secret-private-value"
WEB_CALLBACK_URL = "https://api.jobpilot.example.invalid/api/v1/auth/web/callback"
EMAIL_CLAIM = "https://jobpilot.example.invalid/claims/email"
EMAIL_VERIFIED_CLAIM = "https://jobpilot.example.invalid/claims/email_verified"
STATE = "state-browser-bound-value"
NONCE = "nonce-browser-bound-value"
PKCE_VERIFIER = "pkce-verifier-browser-bound-value-with-sufficient-entropy-0123456789"
AUTHORIZATION_CODE = "authorization-code-private-value+/="
PROVIDER_DETAIL = "provider-private-diagnostic-detail"


def _settings(**overrides: object) -> AuthSettings:
    values = {
        "issuer": ISSUER,
        "jwks_url": JWKS_URL,
        "authorize_url": AUTHORIZE_URL,
        "token_url": TOKEN_URL,
        "audience": AUDIENCE,
        "extension_client_id": EXTENSION_CLIENT_ID,
        "web_client_id": WEB_CLIENT_ID,
        "web_client_secret": WEB_CLIENT_SECRET,
        "web_origin": "https://api.jobpilot.example.invalid",
        "web_callback_url": WEB_CALLBACK_URL,
        "access_token_email_claim": EMAIL_CLAIM,
        "access_token_email_verified_claim": EMAIL_VERIFIED_CLAIM,
        "clock_skew_seconds": 60,
        "jwks_cache_seconds": 300,
        "jwks_timeout_seconds": 5.0,
    }
    values.update(overrides)
    return AuthSettings(**values)


def _private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _claims(**overrides: object) -> dict[str, object]:
    now = int(datetime.now(UTC).timestamp())
    values: dict[str, object] = {
        "iss": ISSUER,
        "aud": WEB_CLIENT_ID,
        "exp": now + 300,
        "iat": now - 1,
        "nbf": now - 1,
        "auth_time": now - 30,
        "sub": "auth0|CaseSensitiveSubject",
        "azp": WEB_CLIENT_ID,
        "nonce": NONCE,
        "email": " Person@Example.COM ",
        "email_verified": True,
    }
    values.update(overrides)
    return values


def _encode_id_token(
    private_key: rsa.RSAPrivateKey,
    claims: dict[str, object] | None = None,
    *,
    algorithm: str = "RS256",
    token_type: str | None = "JWT",
    key_id: str | None = "key-1",
) -> str:
    headers: dict[str, object] = {"typ": token_type}
    if key_id is not None:
        headers["kid"] = key_id
    return jwt.encode(
        _claims() if claims is None else claims,
        private_key,
        algorithm=algorithm,
        headers=headers,
    )


def _nonce_hash(nonce: str = NONCE) -> bytes:
    return hashlib.sha256(nonce.encode("ascii")).digest()


class FakeSigningKeyResolver:
    def __init__(self, key: object) -> None:
        self._key = key
        self.requested_key_ids: list[str] = []

    def resolve(self, key_id: str) -> object:
        self.requested_key_ids.append(key_id)
        return self._key


class UnavailableSigningKeyResolver:
    def resolve(self, key_id: str) -> object:
        raise IdentityProviderUnavailableError


class MutableMonotonic:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class TrickleStream(httpx2.SyncByteStream):
    def __init__(self, clock: MutableMonotonic, chunks: tuple[bytes, ...]) -> None:
        self._clock = clock
        self._chunks = chunks

    def __iter__(self) -> Iterator[bytes]:
        for chunk in self._chunks:
            self._clock.now += 3.0
            yield chunk


class RecordingTokenEndpoint:
    def __init__(self, id_token: str) -> None:
        self._id_token = id_token
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return httpx2.Response(
            200,
            json={
                "access_token": "provider-access-token-that-must-be-discarded",
                "id_token": self._id_token,
                "token_type": "Bearer",
                "expires_in": 300,
            },
        )


def _exchange_once(
    id_token: str,
    resolver: SigningKeyResolver,
) -> VerifiedProviderIdentity:
    endpoint = RecordingTokenEndpoint(id_token)
    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        provider = Auth0WebProvider(_settings(), client, resolver)
        return provider.exchange_code(
            code=AUTHORIZATION_CODE,
            pkce_verifier=PKCE_VERIFIER,
            expected_nonce_hash=_nonce_hash(),
        )


def _assert_sanitized(error: BaseException, *sensitive_values: str) -> None:
    rendered = "\n".join(
        (
            str(error),
            repr(error),
            repr(error.args),
            "".join(traceback.format_exception(error)),
        )
    )
    assert str(error) == ""
    for sensitive_value in sensitive_values:
        if sensitive_value:
            assert sensitive_value not in rendered


def test_login_authorization_url_uses_only_the_fixed_oidc_parameters() -> None:
    with httpx2.Client(
        transport=httpx2.MockTransport(lambda request: httpx2.Response(500)),
        trust_env=False,
    ) as client:
        provider = Auth0WebProvider(
            _settings(),
            client,
            FakeSigningKeyResolver(_private_key().public_key()),
        )

        authorization_url = provider.authorization_url(
            intent="login",
            state=STATE,
            nonce=NONCE,
            pkce_verifier=PKCE_VERIFIER,
        )

    parsed = urlsplit(authorization_url)
    query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    expected_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(PKCE_VERIFIER.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    expected_query = {
        "response_type": "code",
        "client_id": WEB_CLIENT_ID,
        "redirect_uri": WEB_CALLBACK_URL,
        "scope": "openid profile email",
        "state": STATE,
        "nonce": NONCE,
        "code_challenge": expected_challenge,
        "code_challenge_method": "S256",
        "prompt": "login",
    }
    assert urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", "")) == AUTHORIZE_URL
    assert dict(query) == expected_query
    assert len(query) == len(expected_query)
    assert parsed.fragment == ""
    assert WEB_CLIENT_SECRET not in authorization_url
    assert PKCE_VERIFIER not in authorization_url
    assert "offline_access" not in authorization_url


def test_signup_authorization_url_uses_only_screen_hint_without_expanding_scope() -> None:
    with httpx2.Client(
        transport=httpx2.MockTransport(lambda request: httpx2.Response(500)),
        trust_env=False,
    ) as client:
        provider = Auth0WebProvider(
            _settings(),
            client,
            FakeSigningKeyResolver(_private_key().public_key()),
        )

        authorization_url = provider.authorization_url(
            intent="signup",
            state=STATE,
            nonce=NONCE,
            pkce_verifier=PKCE_VERIFIER,
        )

    parsed = urlsplit(authorization_url)
    query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    expected_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(PKCE_VERIFIER.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    expected_query = {
        "response_type": "code",
        "client_id": WEB_CLIENT_ID,
        "redirect_uri": WEB_CALLBACK_URL,
        "scope": "openid profile email",
        "state": STATE,
        "nonce": NONCE,
        "code_challenge": expected_challenge,
        "code_challenge_method": "S256",
        "screen_hint": "signup",
    }
    assert urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", "")) == AUTHORIZE_URL
    assert dict(query) == expected_query
    assert len(query) == len(expected_query)


@pytest.mark.parametrize("intent", ["", "reauth", "extension", "LOGIN"])
def test_authorization_url_rejects_every_non_task6_intent(intent: str) -> None:
    with httpx2.Client(
        transport=httpx2.MockTransport(lambda request: httpx2.Response(500)),
        trust_env=False,
    ) as client:
        provider = Auth0WebProvider(
            _settings(),
            client,
            FakeSigningKeyResolver(_private_key().public_key()),
        )

        with pytest.raises(ValueError) as captured:
            provider.authorization_url(
                intent=intent,
                state=STATE,
                nonce=NONCE,
                pkce_verifier=PKCE_VERIFIER,
            )

    assert STATE not in str(captured.value)
    assert NONCE not in str(captured.value)
    assert PKCE_VERIFIER not in str(captured.value)


def test_exchange_posts_the_exact_confidential_client_form_to_the_fixed_token_url() -> None:
    private_key = _private_key()
    endpoint = RecordingTokenEndpoint(_encode_id_token(private_key))
    resolver = FakeSigningKeyResolver(private_key.public_key())

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        provider = Auth0WebProvider(_settings(), client, resolver)
        identity = provider.exchange_code(
            code=AUTHORIZATION_CODE,
            pkce_verifier=PKCE_VERIFIER,
            expected_nonce_hash=_nonce_hash(),
        )

    assert identity.subject == "auth0|CaseSensitiveSubject"
    assert len(endpoint.requests) == 1
    request = endpoint.requests[0]
    assert request.method == "POST"
    assert str(request.url) == TOKEN_URL
    assert request.headers["content-type"].split(";", 1)[0] == "application/x-www-form-urlencoded"
    form = parse_qsl(request.content.decode("ascii"), keep_blank_values=True)
    expected_form = {
        "grant_type": "authorization_code",
        "client_id": WEB_CLIENT_ID,
        "client_secret": WEB_CLIENT_SECRET,
        "code": AUTHORIZATION_CODE,
        "redirect_uri": WEB_CALLBACK_URL,
        "code_verifier": PKCE_VERIFIER,
    }
    assert dict(form) == expected_form
    assert len(form) == len(expected_form)


def test_exchange_does_not_follow_redirects_from_the_fixed_token_endpoint() -> None:
    requests: list[httpx2.Request] = []

    def endpoint(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        if str(request.url) == TOKEN_URL:
            return httpx2.Response(
                302,
                headers={"Location": f"https://attacker.invalid/{PROVIDER_DETAIL}"},
            )
        pytest.fail("The provider followed a token-endpoint redirect")

    with httpx2.Client(
        transport=httpx2.MockTransport(endpoint),
        follow_redirects=True,
        trust_env=False,
    ) as client:
        provider = Auth0WebProvider(
            _settings(),
            client,
            FakeSigningKeyResolver(_private_key().public_key()),
        )
        with pytest.raises(IdentityProviderResponseError) as captured:
            provider.exchange_code(
                code=AUTHORIZATION_CODE,
                pkce_verifier=PKCE_VERIFIER,
                expected_nonce_hash=_nonce_hash(),
            )

    assert len(requests) == 1
    assert str(requests[0].url) == TOKEN_URL
    _assert_sanitized(
        captured.value,
        AUTHORIZATION_CODE,
        PKCE_VERIFIER,
        WEB_CLIENT_SECRET,
        PROVIDER_DETAIL,
        "attacker.invalid",
    )


def test_valid_rs256_id_token_returns_a_provider_neutral_identity() -> None:
    private_key = _private_key()
    claims = _claims()
    resolver = FakeSigningKeyResolver(private_key.public_key())

    identity = _exchange_once(_encode_id_token(private_key, claims), resolver)

    assert identity == VerifiedProviderIdentity(
        issuer=ISSUER,
        subject="auth0|CaseSensitiveSubject",
        verified_email=" Person@Example.COM ",
        authorized_party=WEB_CLIENT_ID,
        authentication_time=datetime.fromtimestamp(claims["auth_time"], UTC),  # type: ignore[arg-type]
    )
    assert resolver.requested_key_ids == ["key-1"]


def test_id_token_accepts_omitted_optional_authorized_party() -> None:
    private_key = _private_key()
    claims = _claims()
    del claims["azp"]

    identity = _exchange_once(
        _encode_id_token(private_key, claims),
        FakeSigningKeyResolver(private_key.public_key()),
    )

    assert identity.authorized_party == WEB_CLIENT_ID


def test_multiple_id_token_audiences_require_the_authorized_party() -> None:
    private_key = _private_key()
    claims = _claims(aud=[WEB_CLIENT_ID, "another-client-id"])
    del claims["azp"]
    raw_token = _encode_id_token(private_key, claims)

    with pytest.raises(InvalidIdTokenError):
        _exchange_once(raw_token, FakeSigningKeyResolver(private_key.public_key()))


@pytest.mark.parametrize(
    ("claim_name", "invalid_value"),
    [
        ("exp", 0),
        ("iat", 4_102_444_800),
        ("nbf", 4_102_444_800),
    ],
    ids=["expired", "future-issued-at", "future-not-before"],
)
def test_id_token_rejects_invalid_time_claims(
    claim_name: str,
    invalid_value: int,
) -> None:
    private_key = _private_key()
    raw_token = _encode_id_token(
        private_key,
        _claims(**{claim_name: invalid_value}),
    )

    with pytest.raises(InvalidIdTokenError) as captured:
        _exchange_once(raw_token, FakeSigningKeyResolver(private_key.public_key()))

    _assert_sanitized(captured.value, raw_token, AUTHORIZATION_CODE, WEB_CLIENT_SECRET)


def test_id_token_rejects_authentication_time_after_the_issue_window() -> None:
    private_key = _private_key()
    claims = _claims()
    issued_at = claims["iat"]
    assert isinstance(issued_at, int)
    claims["auth_time"] = issued_at + 61
    raw_token = _encode_id_token(private_key, claims)

    with pytest.raises(InvalidIdTokenError) as captured:
        _exchange_once(raw_token, FakeSigningKeyResolver(private_key.public_key()))

    _assert_sanitized(captured.value, raw_token, AUTHORIZATION_CODE, WEB_CLIENT_SECRET)


@pytest.mark.parametrize(
    "missing_claim",
    ["iss", "aud", "exp", "iat", "sub", "nonce", "email", "email_verified"],
)
def test_id_token_rejects_missing_required_identity_claims(missing_claim: str) -> None:
    private_key = _private_key()
    claims = _claims()
    del claims[missing_claim]
    raw_token = _encode_id_token(private_key, claims)
    expected_error = (
        WebProviderEmailVerificationRequiredError
        if missing_claim == "email_verified"
        else InvalidIdTokenError
    )

    with pytest.raises(expected_error) as captured:
        _exchange_once(raw_token, FakeSigningKeyResolver(private_key.public_key()))

    _assert_sanitized(captured.value, raw_token, AUTHORIZATION_CODE, WEB_CLIENT_SECRET)


@pytest.mark.parametrize(
    ("claim_name", "invalid_value"),
    [
        ("sub", ""),
        ("sub", "   "),
        ("sub", 123),
        ("email", ""),
        ("email", "   "),
        ("email", 123),
        ("email", "a" * 255),
    ],
)
def test_id_token_rejects_malformed_subject_and_email(
    claim_name: str,
    invalid_value: object,
) -> None:
    private_key = _private_key()
    raw_token = _encode_id_token(
        private_key,
        _claims(**{claim_name: invalid_value}),
    )

    with pytest.raises(InvalidIdTokenError) as captured:
        _exchange_once(raw_token, FakeSigningKeyResolver(private_key.public_key()))

    _assert_sanitized(captured.value, raw_token, AUTHORIZATION_CODE, WEB_CLIENT_SECRET)


@pytest.mark.parametrize(
    ("claim_name", "invalid_value"),
    [
        ("nonce", "wrong-nonce-private-value"),
        ("aud", AUDIENCE),
        ("iss", "https://attacker.invalid/"),
        ("azp", EXTENSION_CLIENT_ID),
    ],
)
def test_wrong_nonce_audience_issuer_or_authorized_party_is_rejected_and_sanitized(
    claim_name: str,
    invalid_value: str,
) -> None:
    private_key = _private_key()
    raw_token = _encode_id_token(private_key, _claims(**{claim_name: invalid_value}))

    with pytest.raises(InvalidIdTokenError) as captured:
        _exchange_once(raw_token, FakeSigningKeyResolver(private_key.public_key()))

    _assert_sanitized(
        captured.value,
        raw_token,
        invalid_value,
        AUTHORIZATION_CODE,
        PKCE_VERIFIER,
        WEB_CLIENT_SECRET,
    )


def test_wrong_id_token_signature_is_rejected_and_sanitized() -> None:
    trusted_key = _private_key()
    attacker_key = _private_key()
    raw_token = _encode_id_token(attacker_key)

    with pytest.raises(InvalidIdTokenError) as captured:
        _exchange_once(raw_token, FakeSigningKeyResolver(trusted_key.public_key()))

    _assert_sanitized(
        captured.value,
        raw_token,
        AUTHORIZATION_CODE,
        PKCE_VERIFIER,
        WEB_CLIENT_SECRET,
    )


@pytest.mark.parametrize("email_verified", [False, None, "true", 1])
def test_unverified_or_malformed_email_verification_is_rejected_and_sanitized(
    email_verified: object,
) -> None:
    private_key = _private_key()
    raw_token = _encode_id_token(private_key, _claims(email_verified=email_verified))

    with pytest.raises(WebProviderEmailVerificationRequiredError) as captured:
        _exchange_once(raw_token, FakeSigningKeyResolver(private_key.public_key()))

    _assert_sanitized(
        captured.value,
        raw_token,
        AUTHORIZATION_CODE,
        PKCE_VERIFIER,
        WEB_CLIENT_SECRET,
    )


@pytest.mark.parametrize(
    ("algorithm", "token_type", "key_id"),
    [
        ("RS512", "JWT", "key-1"),
        ("RS256", "at+jwt", "key-1"),
        ("RS256", None, "key-1"),
        ("RS256", "JWT", None),
        ("RS256", "JWT", ""),
        ("RS256", "JWT", "k" * 129),
    ],
)
def test_untrusted_id_token_header_requires_rs256_jwt_and_a_bounded_key_id(
    algorithm: str,
    token_type: str | None,
    key_id: str | None,
) -> None:
    private_key = _private_key()
    raw_token = _encode_id_token(
        private_key,
        algorithm=algorithm,
        token_type=token_type,
        key_id=key_id,
    )
    resolver = FakeSigningKeyResolver(private_key.public_key())

    with pytest.raises(InvalidIdTokenError) as captured:
        _exchange_once(raw_token, resolver)

    assert resolver.requested_key_ids == []
    _assert_sanitized(
        captured.value,
        raw_token,
        AUTHORIZATION_CODE,
        PKCE_VERIFIER,
        WEB_CLIENT_SECRET,
    )


@pytest.mark.parametrize(
    "raw_token",
    [
        "malformed-id-token-private-value",
        "x" * 16_385,
    ],
    ids=["malformed", "oversized"],
)
def test_malformed_or_oversized_id_token_is_rejected_before_key_resolution(
    raw_token: str,
) -> None:
    resolver = FakeSigningKeyResolver(_private_key().public_key())

    with pytest.raises(InvalidIdTokenError) as captured:
        _exchange_once(raw_token, resolver)

    assert resolver.requested_key_ids == []
    _assert_sanitized(
        captured.value,
        raw_token,
        AUTHORIZATION_CODE,
        PKCE_VERIFIER,
        WEB_CLIENT_SECRET,
    )


@pytest.mark.parametrize("case", ["oauth_error", "invalid_json", "missing_id_token", "wrong_type"])
def test_untrusted_token_endpoint_responses_fail_with_a_sanitized_error(case: str) -> None:
    def endpoint(request: httpx2.Request) -> httpx2.Response:
        if case == "oauth_error":
            return httpx2.Response(
                400,
                json={"error": "invalid_grant", "error_description": PROVIDER_DETAIL},
            )
        if case == "invalid_json":
            return httpx2.Response(200, text=f"not-json-{PROVIDER_DETAIL}")
        if case == "missing_id_token":
            return httpx2.Response(200, json={"access_token": PROVIDER_DETAIL})
        return httpx2.Response(200, json={"id_token": {"detail": PROVIDER_DETAIL}})

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        provider = Auth0WebProvider(
            _settings(),
            client,
            FakeSigningKeyResolver(_private_key().public_key()),
        )
        with pytest.raises(IdentityProviderResponseError) as captured:
            provider.exchange_code(
                code=AUTHORIZATION_CODE,
                pkce_verifier=PKCE_VERIFIER,
                expected_nonce_hash=_nonce_hash(),
            )

    _assert_sanitized(
        captured.value,
        AUTHORIZATION_CODE,
        PKCE_VERIFIER,
        WEB_CLIENT_SECRET,
        PROVIDER_DETAIL,
    )


@pytest.mark.parametrize(
    ("headers", "content"),
    [
        ({"Content-Type": "application/json"}, b"x" * 65_537),
        (
            {"Content-Type": "application/json", "Content-Encoding": "gzip"},
            b"{}",
        ),
    ],
    ids=["oversized", "non-identity-encoding"],
)
def test_token_endpoint_rejects_unbounded_or_encoded_responses(
    headers: dict[str, str],
    content: bytes,
) -> None:
    def endpoint(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, headers=headers, content=content)

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        provider = Auth0WebProvider(
            _settings(),
            client,
            FakeSigningKeyResolver(_private_key().public_key()),
        )
        with pytest.raises(IdentityProviderResponseError) as captured:
            provider.exchange_code(
                code=AUTHORIZATION_CODE,
                pkce_verifier=PKCE_VERIFIER,
                expected_nonce_hash=_nonce_hash(),
            )

    _assert_sanitized(
        captured.value,
        AUTHORIZATION_CODE,
        PKCE_VERIFIER,
        WEB_CLIENT_SECRET,
    )


def test_token_exchange_enforces_a_total_wall_clock_deadline() -> None:
    clock = MutableMonotonic()

    def endpoint(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            headers={"Content-Type": "application/json"},
            stream=TrickleStream(clock, (b'{"id_token":"', b'never-finished"}')),
        )

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        provider = Auth0WebProvider(
            _settings(jwks_timeout_seconds=5.0),
            client,
            FakeSigningKeyResolver(_private_key().public_key()),
            monotonic=clock,
        )
        with pytest.raises(WebProviderUnavailableError) as captured:
            provider.exchange_code(
                code=AUTHORIZATION_CODE,
                pkce_verifier=PKCE_VERIFIER,
                expected_nonce_hash=_nonce_hash(),
            )

    _assert_sanitized(
        captured.value,
        AUTHORIZATION_CODE,
        PKCE_VERIFIER,
        WEB_CLIENT_SECRET,
    )


def test_signing_key_resolver_outage_maps_to_provider_unavailable() -> None:
    private_key = _private_key()
    raw_token = _encode_id_token(private_key)

    with pytest.raises(WebProviderUnavailableError) as captured:
        _exchange_once(raw_token, UnavailableSigningKeyResolver())

    _assert_sanitized(
        captured.value,
        raw_token,
        AUTHORIZATION_CODE,
        PKCE_VERIFIER,
        WEB_CLIENT_SECRET,
    )


@pytest.mark.parametrize("invalid_code", ["", "非ascii", "x" * 4_097])
def test_invalid_authorization_code_maps_to_provider_rejection(invalid_code: str) -> None:
    requests: list[httpx2.Request] = []

    def endpoint(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(500)

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        provider = Auth0WebProvider(
            _settings(),
            client,
            FakeSigningKeyResolver(_private_key().public_key()),
        )
        with pytest.raises(WebProviderRejectedError) as captured:
            provider.exchange_code(
                code=invalid_code,
                pkce_verifier=PKCE_VERIFIER,
                expected_nonce_hash=_nonce_hash(),
            )

    assert requests == []
    _assert_sanitized(captured.value, invalid_code, PKCE_VERIFIER, WEB_CLIENT_SECRET)


def test_token_endpoint_outage_fails_with_a_sanitized_unavailable_error() -> None:
    def endpoint(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError(PROVIDER_DETAIL, request=request)

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        provider = Auth0WebProvider(
            _settings(),
            client,
            FakeSigningKeyResolver(_private_key().public_key()),
        )
        with pytest.raises(WebProviderUnavailableError) as captured:
            provider.exchange_code(
                code=AUTHORIZATION_CODE,
                pkce_verifier=PKCE_VERIFIER,
                expected_nonce_hash=_nonce_hash(),
            )

    _assert_sanitized(
        captured.value,
        AUTHORIZATION_CODE,
        PKCE_VERIFIER,
        WEB_CLIENT_SECRET,
        PROVIDER_DETAIL,
    )
