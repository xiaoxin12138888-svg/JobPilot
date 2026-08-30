from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock

import httpx2
import jwt

from jobpilot_api.config import AuthSettings
from jobpilot_api.domain.identity import VerifiedProviderIdentity

ALGORITHM = "RS256"
TOKEN_TYPE = "JWT"
MAX_TOKEN_LENGTH = 16_384
MAX_KEY_ID_LENGTH = 128
MAX_JWKS_BYTES = 65_536
MAX_JWKS_KEYS = 32
MINIMUM_RSA_KEY_BITS = 2_048
JWKS_RETRY_SECONDS = 5.0
RSA_PRIVATE_JWK_MEMBERS = frozenset({"d", "p", "q", "dp", "dq", "qi", "oth"})


class InvalidAccessTokenError(Exception):
    """The credential does not satisfy the Extension access-token contract."""


class EmailVerificationRequiredError(Exception):
    """The signed provider identity has not completed email verification."""


class IdentityProviderUnavailableError(Exception):
    """The configured provider could not supply trustworthy signing keys."""


class _UnknownSigningKeyError(Exception):
    pass


class _InvalidJwksError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class _JwksSnapshot:
    generation: int
    keys_by_id: dict[str, object]
    expires_at: float


class ExtensionAccessTokenValidator:
    """Thread-safe, process-scoped validator for one configured issuer.

    The validator and its injected HTTP client must share the application
    lifespan. Recreating either per request defeats the JWKS cache,
    single-flight lock, and bounded unknown-key refresh state.
    """

    def __init__(
        self,
        settings: AuthSettings,
        http_client: httpx2.Client,
        *,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._http_client = http_client
        self._monotonic = monotonic
        self._lock = Lock()
        self._snapshot: _JwksSnapshot | None = None
        self._generation = 0
        self._unknown_refresh_consumed_generation: int | None = None
        self._unknown_refresh_failed_generation: int | None = None
        self._retry_not_before = 0.0

    def validate(self, raw_token: str) -> VerifiedProviderIdentity:
        kid = _read_key_id(raw_token)
        try:
            signing_key = self._get_signing_key(kid)
        except _UnknownSigningKeyError:
            raise InvalidAccessTokenError from None

        try:
            decoded = jwt.decode_complete(
                raw_token,
                key=signing_key,
                algorithms=[ALGORITHM],
                issuer=self._settings.issuer,
                audience=self._settings.audience,
                leeway=self._settings.clock_skew_seconds,
                options={
                    "verify_signature": True,
                    "verify_iss": True,
                    "verify_aud": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True,
                    "verify_sub": True,
                    "require": [
                        "iss",
                        "aud",
                        "exp",
                        "iat",
                        "sub",
                        "azp",
                        self._settings.access_token_email_claim,
                        self._settings.access_token_email_verified_claim,
                    ],
                    "strict_aud": False,
                    "enforce_minimum_key_length": True,
                },
            )
            return self._to_verified_identity(decoded["payload"])
        except (
            jwt.PyJWTError,
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
            RecursionError,
        ):
            raise InvalidAccessTokenError from None

    def _get_signing_key(self, kid: str) -> object:
        with self._lock:
            now = self._monotonic()
            snapshot = self._snapshot
            loaded_current_generation = snapshot is None or now >= snapshot.expires_at
            if loaded_current_generation:
                if now < self._retry_not_before:
                    raise IdentityProviderUnavailableError
                try:
                    keys_by_id = self._fetch_keys()
                except IdentityProviderUnavailableError:
                    self._retry_not_before = self._monotonic() + JWKS_RETRY_SECONDS
                    raise
                snapshot = self._publish(keys_by_id, self._monotonic())

            signing_key = snapshot.keys_by_id.get(kid)
            if signing_key is not None:
                return signing_key

            if loaded_current_generation:
                self._unknown_refresh_consumed_generation = snapshot.generation
                raise _UnknownSigningKeyError
            if self._unknown_refresh_consumed_generation == snapshot.generation:
                if self._unknown_refresh_failed_generation == snapshot.generation:
                    raise IdentityProviderUnavailableError
                raise _UnknownSigningKeyError

            self._unknown_refresh_consumed_generation = snapshot.generation
            try:
                keys_by_id = self._fetch_keys()
            except IdentityProviderUnavailableError:
                self._unknown_refresh_failed_generation = snapshot.generation
                self._retry_not_before = self._monotonic() + JWKS_RETRY_SECONDS
                raise
            refreshed = self._publish(keys_by_id, self._monotonic())
            self._unknown_refresh_consumed_generation = refreshed.generation
            signing_key = refreshed.keys_by_id.get(kid)
            if signing_key is None:
                raise _UnknownSigningKeyError
            return signing_key

    def _publish(self, keys_by_id: dict[str, object], now: float) -> _JwksSnapshot:
        self._generation += 1
        snapshot = _JwksSnapshot(
            generation=self._generation,
            keys_by_id=keys_by_id,
            expires_at=now + self._settings.jwks_cache_seconds,
        )
        self._snapshot = snapshot
        self._unknown_refresh_failed_generation = None
        self._retry_not_before = 0.0
        return snapshot

    def _fetch_keys(self) -> dict[str, object]:
        try:
            deadline = self._monotonic() + self._settings.jwks_timeout_seconds
            body = bytearray()
            with self._http_client.stream(
                "GET",
                self._settings.jwks_url,
                headers={"Accept": "application/json", "Accept-Encoding": "identity"},
                follow_redirects=False,
                timeout=self._settings.jwks_timeout_seconds,
            ) as response:
                if self._monotonic() >= deadline:
                    raise _InvalidJwksError
                response.raise_for_status()
                content_encoding = response.headers.get("Content-Encoding")
                if content_encoding is not None and content_encoding.strip().lower() not in {
                    "",
                    "identity",
                }:
                    raise _InvalidJwksError
                for chunk in response.iter_bytes():
                    if self._monotonic() >= deadline:
                        raise _InvalidJwksError
                    if len(body) + len(chunk) > MAX_JWKS_BYTES:
                        raise _InvalidJwksError
                    body.extend(chunk)
            document = json.loads(body)
            return _parse_jwks(document)
        except (
            httpx2.HTTPError,
            jwt.PyJWTError,
            _InvalidJwksError,
            KeyError,
            OverflowError,
            RecursionError,
            TypeError,
            ValueError,
        ):
            raise IdentityProviderUnavailableError from None

    def _to_verified_identity(self, payload: dict[str, object]) -> VerifiedProviderIdentity:
        for claim_name in ("exp", "iat"):
            if type(payload.get(claim_name)) is not int:
                raise InvalidAccessTokenError
        if "nbf" in payload and type(payload["nbf"]) is not int:
            raise InvalidAccessTokenError

        subject = payload.get("sub")
        authorized_party = payload.get("azp")
        verified_email = payload.get(self._settings.access_token_email_claim)
        email_verified = payload.get(self._settings.access_token_email_verified_claim)
        if not isinstance(subject, str) or not subject.strip():
            raise InvalidAccessTokenError
        if authorized_party != self._settings.extension_client_id:
            raise InvalidAccessTokenError
        if not isinstance(verified_email, str) or not verified_email.strip():
            raise InvalidAccessTokenError
        if len(verified_email.strip()) > 254:
            raise InvalidAccessTokenError
        if email_verified is False:
            raise EmailVerificationRequiredError
        if email_verified is not True:
            raise InvalidAccessTokenError

        return VerifiedProviderIdentity(
            issuer=self._settings.issuer,
            subject=subject,
            verified_email=verified_email,
            authorized_party=self._settings.extension_client_id,
        )


def _read_key_id(raw_token: str) -> str:
    if type(raw_token) is not str or not raw_token or len(raw_token) > MAX_TOKEN_LENGTH:
        raise InvalidAccessTokenError
    try:
        header = jwt.get_unverified_header(raw_token)
    except (jwt.PyJWTError, TypeError, ValueError, RecursionError):
        raise InvalidAccessTokenError from None
    kid = header.get("kid")
    if (
        header.get("alg") != ALGORITHM
        or header.get("typ") != TOKEN_TYPE
        or not isinstance(kid, str)
        or not kid
        or len(kid) > MAX_KEY_ID_LENGTH
    ):
        raise InvalidAccessTokenError
    return kid


def _parse_jwks(document: object) -> dict[str, object]:
    if not isinstance(document, dict):
        raise _InvalidJwksError
    raw_keys = document.get("keys")
    if not isinstance(raw_keys, list) or not raw_keys or len(raw_keys) > MAX_JWKS_KEYS:
        raise _InvalidJwksError

    keys_by_id: dict[str, object] = {}
    for raw_key in raw_keys:
        if not isinstance(raw_key, dict):
            raise _InvalidJwksError
        if not _is_eligible_signing_key(raw_key):
            continue
        kid = raw_key.get("kid")
        if not isinstance(kid, str) or not kid or len(kid) > MAX_KEY_ID_LENGTH:
            raise _InvalidJwksError
        if kid in keys_by_id:
            raise _InvalidJwksError
        parsed_key = jwt.PyJWK.from_dict(raw_key, algorithm=ALGORITHM).key
        if getattr(parsed_key, "key_size", 0) < MINIMUM_RSA_KEY_BITS:
            raise _InvalidJwksError
        keys_by_id[kid] = parsed_key

    if not keys_by_id:
        raise _InvalidJwksError
    return keys_by_id


def _is_eligible_signing_key(raw_key: dict[object, object]) -> bool:
    if raw_key.get("kty") != "RSA":
        return False
    if any(member in raw_key for member in RSA_PRIVATE_JWK_MEMBERS):
        raise _InvalidJwksError
    if raw_key.get("alg") not in (None, ALGORITHM):
        return False
    if raw_key.get("use") not in (None, "sig"):
        return False
    key_operations = raw_key.get("key_ops")
    if key_operations is None:
        return True
    if not isinstance(key_operations, list) or not all(
        isinstance(operation, str) for operation in key_operations
    ):
        raise _InvalidJwksError
    return "verify" in key_operations
