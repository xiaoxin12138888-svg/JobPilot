from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock

import httpx2
import jwt

from jobpilot_api.config import AuthSettings

ALGORITHM = "RS256"
TOKEN_TYPE = "JWT"
MAX_TOKEN_LENGTH = 16_384
MAX_KEY_ID_LENGTH = 128
MAX_JWKS_BYTES = 65_536
MAX_JWKS_KEYS = 32
MINIMUM_RSA_KEY_BITS = 2_048
JWKS_RETRY_SECONDS = 5.0
RSA_PRIVATE_JWK_MEMBERS = frozenset({"d", "p", "q", "dp", "dq", "qi", "oth"})


class InvalidTokenHeaderError(Exception):
    """A JWT header cannot select an approved signing key."""


class UnknownSigningKeyError(Exception):
    """The token references no key in the bounded provider snapshot."""


class IdentityProviderUnavailableError(Exception):
    """The configured provider could not supply trustworthy signing keys."""


class _InvalidJwksError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class _JwksSnapshot:
    generation: int
    keys_by_id: dict[str, object]
    expires_at: float


class JwksResolver:
    """Thread-safe, process-scoped signing-key resolver for one issuer."""

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

    def resolve(self, key_id: str) -> object:
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

            signing_key = snapshot.keys_by_id.get(key_id)
            if signing_key is not None:
                return signing_key

            if loaded_current_generation:
                self._unknown_refresh_consumed_generation = snapshot.generation
                raise UnknownSigningKeyError
            if self._unknown_refresh_consumed_generation == snapshot.generation:
                if self._unknown_refresh_failed_generation == snapshot.generation:
                    raise IdentityProviderUnavailableError
                raise UnknownSigningKeyError

            self._unknown_refresh_consumed_generation = snapshot.generation
            try:
                keys_by_id = self._fetch_keys()
            except IdentityProviderUnavailableError:
                self._unknown_refresh_failed_generation = snapshot.generation
                self._retry_not_before = self._monotonic() + JWKS_RETRY_SECONDS
                raise
            refreshed = self._publish(keys_by_id, self._monotonic())
            self._unknown_refresh_consumed_generation = refreshed.generation
            signing_key = refreshed.keys_by_id.get(key_id)
            if signing_key is None:
                raise UnknownSigningKeyError
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


def read_signing_key_id(raw_token: str) -> str:
    if type(raw_token) is not str or not raw_token or len(raw_token) > MAX_TOKEN_LENGTH:
        raise InvalidTokenHeaderError
    try:
        header = jwt.get_unverified_header(raw_token)
    except (jwt.PyJWTError, TypeError, ValueError, RecursionError):
        raise InvalidTokenHeaderError from None
    key_id = header.get("kid")
    if (
        header.get("alg") != ALGORITHM
        or header.get("typ") != TOKEN_TYPE
        or not isinstance(key_id, str)
        or not key_id
        or len(key_id) > MAX_KEY_ID_LENGTH
    ):
        raise InvalidTokenHeaderError
    return key_id


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
        key_id = raw_key.get("kid")
        if not isinstance(key_id, str) or not key_id or len(key_id) > MAX_KEY_ID_LENGTH:
            raise _InvalidJwksError
        if key_id in keys_by_id:
            raise _InvalidJwksError
        parsed_key = jwt.PyJWK.from_dict(raw_key, algorithm=ALGORITHM).key
        if getattr(parsed_key, "key_size", 0) < MINIMUM_RSA_KEY_BITS:
            raise _InvalidJwksError
        keys_by_id[key_id] = parsed_key

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
