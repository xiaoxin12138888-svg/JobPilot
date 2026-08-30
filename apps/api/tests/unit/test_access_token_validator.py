from __future__ import annotations

import base64
import gzip
import json
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import httpx2
import jwt
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
from jwt.algorithms import RSAAlgorithm

from jobpilot_api.config import AuthSettings
from jobpilot_api.infrastructure.auth.access_token_validator import (
    EmailVerificationRequiredError,
    ExtensionAccessTokenValidator,
    IdentityProviderUnavailableError,
    InvalidAccessTokenError,
)

ISSUER = "https://tenant.example.invalid/"
JWKS_URL = "https://tenant.example.invalid/.well-known/jwks.json"
TOKEN_URL = "https://tenant.example.invalid/oauth/token"
AUDIENCE = "https://api.jobpilot.example.invalid"
EXTENSION_CLIENT_ID = "extension-client-id"
EMAIL_CLAIM = "https://jobpilot.example.invalid/claims/email"
EMAIL_VERIFIED_CLAIM = "https://jobpilot.example.invalid/claims/email_verified"


def _settings(**overrides: object) -> AuthSettings:
    values = {
        "issuer": ISSUER,
        "jwks_url": JWKS_URL,
        "authorize_url": "https://tenant.example.invalid/authorize",
        "token_url": TOKEN_URL,
        "audience": AUDIENCE,
        "extension_client_id": EXTENSION_CLIENT_ID,
        "web_client_id": "web-client-id",
        "web_client_secret": "web-client-secret",
        "web_origin": "https://api.jobpilot.example.invalid",
        "web_callback_url": ("https://api.jobpilot.example.invalid/api/v1/auth/web/callback"),
        "access_token_email_claim": EMAIL_CLAIM,
        "access_token_email_verified_claim": EMAIL_VERIFIED_CLAIM,
        "clock_skew_seconds": 60,
        "jwks_cache_seconds": 300,
        "jwks_timeout_seconds": 5.0,
    }
    values.update(overrides)
    return AuthSettings(**values)


def _private_key(key_size: int = 2048) -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=key_size)


def _jwk(private_key: rsa.RSAPrivateKey, kid: str) -> dict[str, object]:
    value = RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    assert isinstance(value, dict)
    value.update({"kid": kid, "alg": "RS256", "use": "sig", "key_ops": ["verify"]})
    return value


def _claims(now: int) -> dict[str, object]:
    return {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": now + 300,
        "iat": now - 1,
        "sub": "auth0|CaseSensitiveSubject",
        "azp": EXTENSION_CLIENT_ID,
        EMAIL_CLAIM: " Person@Example.COM ",
        EMAIL_VERIFIED_CLAIM: True,
    }


def _encode(
    private_key: rsa.RSAPrivateKey | str | None,
    kid: str | None,
    claims: dict[str, object],
    *,
    algorithm: str = "RS256",
    token_type: str | None = "JWT",
    extra_headers: dict[str, object] | None = None,
) -> str:
    headers: dict[str, object] = {"typ": token_type}
    if kid is not None:
        headers["kid"] = kid
    if extra_headers is not None:
        headers.update(extra_headers)
    return jwt.encode(claims, private_key, algorithm=algorithm, headers=headers)


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _sign_compact_token(
    private_key: rsa.RSAPrivateKey,
    header: bytes,
    payload: bytes,
) -> str:
    signing_input = f"{_base64url(header)}.{_base64url(payload)}".encode()
    signature = private_key.sign(signing_input, PKCS1v15(), hashes.SHA256())
    return f"{signing_input.decode()}.{_base64url(signature)}"


class RecordingJwksEndpoint:
    def __init__(self, *documents: dict[str, object]) -> None:
        self._documents = documents
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self._documents) - 1)
        return httpx2.Response(200, json=self._documents[index])


class MutableClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


class OversizedJwksStream(httpx2.SyncByteStream):
    def __init__(self) -> None:
        self.chunks_yielded = 0

    def __iter__(self):
        for _ in range(10):
            self.chunks_yielded += 1
            yield b" " * 16_384


class TrackingJwksStream(httpx2.SyncByteStream):
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.chunks_yielded = 0

    def __iter__(self):
        self.chunks_yielded += 1
        yield self._payload


class SlowJwksStream(httpx2.SyncByteStream):
    def __init__(self, clock: MutableClock, payload: bytes) -> None:
        self._clock = clock
        self._chunks = [b" "] * 10 + [payload]
        self.chunks_yielded = 0

    def __iter__(self):
        for chunk in self._chunks:
            self._clock.value += 1
            self.chunks_yielded += 1
            yield chunk


def _validate_once(
    token: str,
    document: dict[str, object],
):
    endpoint = RecordingJwksEndpoint(document)
    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(_settings(), client)
        return validator.validate(token)


def test_valid_extension_access_token_returns_provider_neutral_identity_and_caches_jwks() -> None:
    now = int(datetime.now(UTC).timestamp())
    private_key = _private_key()
    endpoint = RecordingJwksEndpoint({"keys": [_jwk(private_key, "key-1")]})
    token = _encode(private_key, "key-1", _claims(now))

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(_settings(), client)
        first = validator.validate(token)
        second = validator.validate(token)

    assert first == second
    assert first.issuer == ISSUER
    assert first.subject == "auth0|CaseSensitiveSubject"
    assert first.verified_email == " Person@Example.COM "
    assert first.authorized_party == EXTENSION_CLIENT_ID
    assert first.authentication_time is None
    assert len(endpoint.requests) == 1


def test_audience_array_containing_the_fixed_api_audience_is_valid() -> None:
    now = int(datetime.now(UTC).timestamp())
    private_key = _private_key()
    claims = _claims(now)
    claims["aud"] = [AUDIENCE, "https://tenant.example.invalid/userinfo"]

    identity = _validate_once(
        _encode(private_key, "key-1", claims),
        {"keys": [_jwk(private_key, "key-1")]},
    )

    assert identity.subject == "auth0|CaseSensitiveSubject"


@pytest.mark.parametrize(
    ("algorithm", "token_type", "kid"),
    [
        ("none", "JWT", "key-1"),
        ("HS256", "JWT", "key-1"),
        ("RS512", "JWT", "key-1"),
        ("RS256", "at+jwt", "key-1"),
        ("RS256", None, "key-1"),
        ("RS256", "JWT", None),
        ("RS256", "JWT", ""),
    ],
)
def test_untrusted_header_must_use_exact_algorithm_type_and_kid(
    algorithm: str,
    token_type: str | None,
    kid: str | None,
) -> None:
    now = int(datetime.now(UTC).timestamp())
    signing_key: rsa.RSAPrivateKey | str | None = "not-a-private-key" * 2
    if algorithm.startswith("RS"):
        signing_key = _private_key()
    elif algorithm == "none":
        signing_key = None
    endpoint = RecordingJwksEndpoint({"keys": []})
    token = _encode(
        signing_key,
        kid,
        _claims(now),
        algorithm=algorithm,
        token_type=token_type,
    )

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(_settings(), client)
        with pytest.raises(InvalidAccessTokenError):
            validator.validate(token)

    assert endpoint.requests == []


def test_malformed_token_is_rejected_without_fetching_jwks() -> None:
    endpoint = RecordingJwksEndpoint({"keys": []})

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(_settings(), client)
        with pytest.raises(InvalidAccessTokenError):
            validator.validate("not-a-jwt")

    assert endpoint.requests == []


def test_deeply_nested_header_is_safely_rejected_without_fetching_jwks() -> None:
    nested_json = ("[" * 4_000 + "{}" + "]" * 4_000).encode()
    token = f"{_base64url(nested_json)}.{_base64url(b'{}')}.{_base64url(b'x')}"
    endpoint = RecordingJwksEndpoint({"keys": []})
    assert len(token) < 16_384

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(_settings(), client)
        with pytest.raises(InvalidAccessTokenError):
            validator.validate(token)

    assert endpoint.requests == []


def test_deeply_nested_signed_payload_is_safely_rejected() -> None:
    private_key = _private_key()
    header = json.dumps(
        {"alg": "RS256", "typ": "JWT", "kid": "key-1"},
        separators=(",", ":"),
    ).encode()
    nested_payload = ("[" * 4_000 + "{}" + "]" * 4_000).encode()
    token = _sign_compact_token(private_key, header, nested_payload)
    assert len(token) < 16_384

    with pytest.raises(InvalidAccessTokenError):
        _validate_once(token, {"keys": [_jwk(private_key, "key-1")]})


@pytest.mark.parametrize(
    "case",
    [
        "missing_issuer",
        "wrong_issuer",
        "missing_audience",
        "wrong_audience",
        "missing_expiry",
        "expired",
        "missing_issued_at",
        "future_issued_at",
        "future_not_before",
    ],
)
def test_registered_claim_failures_are_rejected(case: str) -> None:
    now = int(datetime.now(UTC).timestamp())
    private_key = _private_key()
    claims = _claims(now)
    if case == "missing_issuer":
        claims.pop("iss")
    elif case == "wrong_issuer":
        claims["iss"] = "https://other.example.invalid/"
    elif case == "missing_audience":
        claims.pop("aud")
    elif case == "wrong_audience":
        claims["aud"] = "https://other-api.example.invalid"
    elif case == "missing_expiry":
        claims.pop("exp")
    elif case == "expired":
        claims["exp"] = now - 120
    elif case == "missing_issued_at":
        claims.pop("iat")
    elif case == "future_issued_at":
        claims["iat"] = now + 120
    elif case == "future_not_before":
        claims["nbf"] = now + 120

    with pytest.raises(InvalidAccessTokenError):
        _validate_once(
            _encode(private_key, "key-1", claims),
            {"keys": [_jwk(private_key, "key-1")]},
        )


@pytest.mark.parametrize(
    ("claim_name", "invalid_value"),
    [
        ("exp", "9999999999"),
        ("iat", True),
        ("iat", []),
        ("nbf", 1.5),
    ],
)
def test_numeric_date_claims_require_exact_integers(
    claim_name: str,
    invalid_value: object,
) -> None:
    now = int(datetime.now(UTC).timestamp())
    private_key = _private_key()
    claims = _claims(now)
    claims[claim_name] = invalid_value

    with pytest.raises(InvalidAccessTokenError):
        _validate_once(
            _encode(private_key, "key-1", claims),
            {"keys": [_jwk(private_key, "key-1")]},
        )


@pytest.mark.parametrize(
    ("claim_name", "invalid_value", "remove"),
    [
        ("sub", "", False),
        ("sub", "   ", False),
        ("sub", 123, False),
        ("sub", None, True),
        ("azp", "wrong-client", False),
        ("azp", 123, False),
        ("azp", None, True),
        (EMAIL_CLAIM, "", False),
        (EMAIL_CLAIM, "   ", False),
        (EMAIL_CLAIM, 123, False),
        (EMAIL_CLAIM, f"{'a' * 245}@example.com", False),
        (EMAIL_CLAIM, None, True),
        (EMAIL_VERIFIED_CLAIM, "true", False),
        (EMAIL_VERIFIED_CLAIM, 1, False),
        (EMAIL_VERIFIED_CLAIM, None, True),
    ],
)
def test_provider_identity_claims_require_strict_shapes(
    claim_name: str,
    invalid_value: object,
    remove: bool,
) -> None:
    now = int(datetime.now(UTC).timestamp())
    private_key = _private_key()
    claims = _claims(now)
    if remove:
        claims.pop(claim_name)
    else:
        claims[claim_name] = invalid_value

    with pytest.raises(InvalidAccessTokenError):
        _validate_once(
            _encode(private_key, "key-1", claims),
            {"keys": [_jwk(private_key, "key-1")]},
        )


def test_signed_unverified_email_has_a_distinct_non_authorizing_error() -> None:
    now = int(datetime.now(UTC).timestamp())
    private_key = _private_key()
    claims = _claims(now)
    claims[EMAIL_VERIFIED_CLAIM] = False

    with pytest.raises(EmailVerificationRequiredError):
        _validate_once(
            _encode(private_key, "key-1", claims),
            {"keys": [_jwk(private_key, "key-1")]},
        )


def test_id_token_profile_claims_do_not_satisfy_access_token_contract() -> None:
    now = int(datetime.now(UTC).timestamp())
    private_key = _private_key()
    claims = _claims(now)
    claims.pop(EMAIL_CLAIM)
    claims.pop(EMAIL_VERIFIED_CLAIM)
    claims.update({"email": "person@example.com", "email_verified": True})

    with pytest.raises(InvalidAccessTokenError):
        _validate_once(
            _encode(private_key, "key-1", claims),
            {"keys": [_jwk(private_key, "key-1")]},
        )


def test_wrong_signature_is_rejected_without_exposing_library_detail() -> None:
    now = int(datetime.now(UTC).timestamp())
    trusted_key = _private_key()
    attacker_key = _private_key()

    with pytest.raises(InvalidAccessTokenError) as captured:
        _validate_once(
            _encode(attacker_key, "key-1", _claims(now)),
            {"keys": [_jwk(trusted_key, "key-1")]},
        )

    assert str(captured.value) == ""


def test_token_header_key_urls_are_ignored() -> None:
    now = int(datetime.now(UTC).timestamp())
    private_key = _private_key()
    endpoint = RecordingJwksEndpoint({"keys": [_jwk(private_key, "key-1")]})
    token = _encode(
        private_key,
        "key-1",
        _claims(now),
        extra_headers={
            "jku": "https://attacker.example.invalid/jwks.json",
            "x5u": "https://attacker.example.invalid/certificate.pem",
        },
    )

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        ExtensionAccessTokenValidator(_settings(), client).validate(token)

    assert [str(request.url) for request in endpoint.requests] == [JWKS_URL]


def test_unknown_kids_trigger_only_one_forced_refresh_per_cache_generation() -> None:
    now = int(datetime.now(UTC).timestamp())
    trusted_key = _private_key()
    unknown_key = _private_key()
    endpoint = RecordingJwksEndpoint({"keys": [_jwk(trusted_key, "trusted-key")]})

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(_settings(), client)
        validator.validate(_encode(trusted_key, "trusted-key", _claims(now)))
        for kid in ("unknown-1", "unknown-2", "unknown-3"):
            with pytest.raises(InvalidAccessTokenError):
                validator.validate(_encode(unknown_key, kid, _claims(now)))

    assert len(endpoint.requests) == 2


def test_one_forced_refresh_accepts_a_rotated_signing_key() -> None:
    now = int(datetime.now(UTC).timestamp())
    old_key = _private_key()
    new_key = _private_key()
    endpoint = RecordingJwksEndpoint(
        {"keys": [_jwk(old_key, "old-key")]},
        {"keys": [_jwk(old_key, "old-key"), _jwk(new_key, "new-key")]},
    )

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(_settings(), client)
        validator.validate(_encode(old_key, "old-key", _claims(now)))
        identity = validator.validate(_encode(new_key, "new-key", _claims(now)))

    assert identity.subject == "auth0|CaseSensitiveSubject"
    assert len(endpoint.requests) == 2


def test_concurrent_unknown_kids_share_one_forced_refresh() -> None:
    now = int(datetime.now(UTC).timestamp())
    trusted_key = _private_key()
    unknown_key = _private_key()
    endpoint = RecordingJwksEndpoint({"keys": [_jwk(trusted_key, "trusted-key")]})

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(_settings(), client)
        validator.validate(_encode(trusted_key, "trusted-key", _claims(now)))

        def reject(kid: str) -> bool:
            with pytest.raises(InvalidAccessTokenError):
                validator.validate(_encode(unknown_key, kid, _claims(now)))
            return True

        with ThreadPoolExecutor(max_workers=8) as executor:
            assert all(executor.map(reject, [f"unknown-{index}" for index in range(8)]))

    assert len(endpoint.requests) == 2


def test_cache_expiry_opens_one_new_generation() -> None:
    now = int(datetime.now(UTC).timestamp())
    trusted_key = _private_key()
    unknown_key = _private_key()
    endpoint = RecordingJwksEndpoint({"keys": [_jwk(trusted_key, "trusted-key")]})
    clock = MutableClock()

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(
            _settings(jwks_cache_seconds=10),
            client,
            monotonic=clock,
        )
        validator.validate(_encode(trusted_key, "trusted-key", _claims(now)))
        with pytest.raises(InvalidAccessTokenError):
            validator.validate(_encode(unknown_key, "unknown-1", _claims(now)))
        clock.value = 11
        with pytest.raises(InvalidAccessTokenError):
            validator.validate(_encode(unknown_key, "unknown-2", _claims(now)))

    assert len(endpoint.requests) == 3


def test_slow_success_starts_cache_lifetime_after_the_fetch_completes() -> None:
    now = int(datetime.now(UTC).timestamp())
    private_key = _private_key()
    requests: list[httpx2.Request] = []
    clock = MutableClock()

    def endpoint(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        clock.value = 20
        return httpx2.Response(200, json={"keys": [_jwk(private_key, "key-1")]})

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(
            _settings(jwks_cache_seconds=10, jwks_timeout_seconds=30),
            client,
            monotonic=clock,
        )
        token = _encode(private_key, "key-1", _claims(now))
        validator.validate(token)
        validator.validate(token)

    assert len(requests) == 1


def test_failed_forced_refresh_keeps_last_known_good_without_false_401() -> None:
    now = int(datetime.now(UTC).timestamp())
    trusted_key = _private_key()
    unknown_key = _private_key()
    requests: list[httpx2.Request] = []
    clock = MutableClock()

    def endpoint(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx2.Response(200, json={"keys": [_jwk(trusted_key, "trusted-key")]})
        if len(requests) == 2:
            raise httpx2.ConnectError("provider-internal-detail", request=request)
        return httpx2.Response(
            200,
            json={
                "keys": [
                    _jwk(trusted_key, "trusted-key"),
                    _jwk(unknown_key, "rotated-key"),
                ]
            },
        )

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(
            _settings(jwks_cache_seconds=10),
            client,
            monotonic=clock,
        )
        trusted_token = _encode(trusted_key, "trusted-key", _claims(now))
        rotated_token = _encode(unknown_key, "rotated-key", _claims(now))
        validator.validate(trusted_token)
        with pytest.raises(IdentityProviderUnavailableError):
            validator.validate(rotated_token)
        validator.validate(trusted_token)
        with pytest.raises(IdentityProviderUnavailableError):
            validator.validate(rotated_token)
        assert len(requests) == 2

        clock.value = 11
        identity = validator.validate(rotated_token)

    assert identity.subject == "auth0|CaseSensitiveSubject"
    assert len(requests) == 3


def test_initial_provider_failure_uses_a_sanitized_unavailable_error() -> None:
    now = int(datetime.now(UTC).timestamp())
    private_key = _private_key()
    sensitive_detail = "provider-body-private-detail"

    def endpoint(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError(sensitive_detail, request=request)

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(_settings(), client)
        with pytest.raises(IdentityProviderUnavailableError) as captured:
            validator.validate(_encode(private_key, "key-1", _claims(now)))

    assert str(captured.value) == ""
    assert sensitive_detail not in "".join(traceback.format_exception(captured.value))


def test_initial_provider_outage_uses_one_fixed_retry_gate() -> None:
    now = int(datetime.now(UTC).timestamp())
    private_key = _private_key()
    requests: list[httpx2.Request] = []
    clock = MutableClock()

    def endpoint(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        raise httpx2.ConnectError("provider unavailable", request=request)

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(
            _settings(),
            client,
            monotonic=clock,
        )
        token = _encode(private_key, "key-1", _claims(now))
        with pytest.raises(IdentityProviderUnavailableError):
            validator.validate(token)
        with pytest.raises(IdentityProviderUnavailableError):
            validator.validate(token)
        clock.value = 6
        with pytest.raises(IdentityProviderUnavailableError):
            validator.validate(token)

    assert len(requests) == 2


def test_slow_failure_starts_retry_gate_after_the_fetch_completes() -> None:
    now = int(datetime.now(UTC).timestamp())
    private_key = _private_key()
    requests: list[httpx2.Request] = []
    clock = MutableClock()

    def endpoint(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        clock.value = 20
        raise httpx2.ConnectError("provider unavailable", request=request)

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(
            _settings(),
            client,
            monotonic=clock,
        )
        token = _encode(private_key, "key-1", _claims(now))
        with pytest.raises(IdentityProviderUnavailableError):
            validator.validate(token)
        with pytest.raises(IdentityProviderUnavailableError):
            validator.validate(token)

    assert len(requests) == 1


@pytest.mark.parametrize(
    "case",
    [
        "http",
        "redirect",
        "json",
        "shape",
        "duplicate",
        "wrong_alg",
        "wrong_use",
        "wrong_ops",
        "private",
        "weak",
        "large",
    ],
)
def test_untrusted_jwks_failures_are_sanitized(case: str) -> None:
    now = int(datetime.now(UTC).timestamp())
    private_key = _private_key()
    token = _encode(private_key, "key-1", _claims(now))

    def endpoint(request: httpx2.Request) -> httpx2.Response:
        if case == "http":
            return httpx2.Response(503, text="private provider response")
        if case == "redirect":
            return httpx2.Response(302, headers={"Location": "https://attacker.invalid/"})
        if case == "json":
            return httpx2.Response(200, content=b"not-json")
        if case == "shape":
            return httpx2.Response(200, json={"keys": ["not-an-object"]})
        if case == "duplicate":
            key = _jwk(private_key, "key-1")
            return httpx2.Response(200, json={"keys": [key, key]})
        if case in {"wrong_alg", "wrong_use", "wrong_ops"}:
            key = _jwk(private_key, "key-1")
            if case == "wrong_alg":
                key["alg"] = "RS512"
            elif case == "wrong_use":
                key["use"] = "enc"
            else:
                key["key_ops"] = ["encrypt"]
            return httpx2.Response(200, json={"keys": [key]})
        if case == "private":
            key = RSAAlgorithm.to_jwk(private_key, as_dict=True)
            assert isinstance(key, dict)
            key.update({"kid": "key-1", "alg": "RS256", "use": "sig", "key_ops": ["verify"]})
            return httpx2.Response(200, json={"keys": [key]})
        if case == "large":
            return httpx2.Response(200, content=b" " * 65_537)
        weak_key = _private_key(1024)
        return httpx2.Response(200, json={"keys": [_jwk(weak_key, "key-1")]})

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(_settings(), client)
        with pytest.raises(IdentityProviderUnavailableError) as captured:
            validator.validate(token)

    rendered = "".join(traceback.format_exception(captured.value))
    assert str(captured.value) == ""
    assert "private provider response" not in rendered
    assert "attacker.invalid" not in rendered


def test_chunked_jwks_body_is_stopped_at_the_size_limit() -> None:
    now = int(datetime.now(UTC).timestamp())
    private_key = _private_key()
    stream = OversizedJwksStream()

    def endpoint(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, stream=stream)

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(_settings(), client)
        with pytest.raises(IdentityProviderUnavailableError):
            validator.validate(_encode(private_key, "key-1", _claims(now)))

    assert stream.chunks_yielded < 10


def test_jwks_fetch_has_a_total_deadline_across_slow_chunks() -> None:
    now = int(datetime.now(UTC).timestamp())
    private_key = _private_key()
    clock = MutableClock()
    document = json.dumps({"keys": [_jwk(private_key, "key-1")]}).encode()
    stream = SlowJwksStream(clock, document)

    def endpoint(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, stream=stream)

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(
            _settings(jwks_timeout_seconds=2.5),
            client,
            monotonic=clock,
        )
        with pytest.raises(IdentityProviderUnavailableError):
            validator.validate(_encode(private_key, "key-1", _claims(now)))

    assert stream.chunks_yielded == 3


def test_encoded_jwks_response_is_rejected_before_decompression() -> None:
    now = int(datetime.now(UTC).timestamp())
    private_key = _private_key()
    stream = TrackingJwksStream(gzip.compress(b" " * 100_000))
    requests: list[httpx2.Request] = []

    def endpoint(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(
            200,
            headers={"Content-Encoding": "gzip"},
            stream=stream,
        )

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(_settings(), client)
        with pytest.raises(IdentityProviderUnavailableError):
            validator.validate(_encode(private_key, "key-1", _claims(now)))

    assert requests[0].headers["Accept-Encoding"] == "identity"
    assert stream.chunks_yielded == 0


def test_deeply_nested_jwks_json_is_a_sanitized_provider_failure() -> None:
    now = int(datetime.now(UTC).timestamp())
    private_key = _private_key()
    nested_json = ("[" * 4_000 + "{}" + "]" * 4_000).encode()

    def endpoint(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=nested_json)

    with httpx2.Client(transport=httpx2.MockTransport(endpoint), trust_env=False) as client:
        validator = ExtensionAccessTokenValidator(_settings(), client)
        with pytest.raises(IdentityProviderUnavailableError):
            validator.validate(_encode(private_key, "key-1", _claims(now)))
