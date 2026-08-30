from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlencode

import httpx2
import jwt

from jobpilot_api.application.web_auth_service import (
    WebProviderEmailVerificationRequiredError,
    WebProviderRejectedError,
    WebProviderUnavailableError,
)
from jobpilot_api.config import AuthSettings
from jobpilot_api.domain.identity import VerifiedProviderIdentity
from jobpilot_api.infrastructure.auth.jwks import (
    ALGORITHM,
    InvalidTokenHeaderError,
    UnknownSigningKeyError,
    read_signing_key_id,
)
from jobpilot_api.infrastructure.auth.jwks import (
    IdentityProviderUnavailableError as JwksUnavailableError,
)

WEB_SCOPE = "openid profile email"
MAX_TOKEN_RESPONSE_BYTES = 65_536
PKCE_VERIFIER_PATTERN = re.compile(r"[A-Za-z0-9._~-]{43,128}\Z")


class InvalidIdTokenError(WebProviderRejectedError):
    """The provider ID token does not satisfy the Web OIDC contract."""


class IdentityProviderResponseError(WebProviderRejectedError):
    """The provider returned a terminal response that cannot establish identity."""


class SigningKeyResolver(Protocol):
    def resolve(self, key_id: str) -> object: ...


class Auth0WebProvider:
    """Auth0-specific Web authorization and OIDC verification boundary."""

    def __init__(
        self,
        settings: AuthSettings,
        http_client: httpx2.Client,
        signing_key_resolver: SigningKeyResolver,
        *,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._http_client = http_client
        self._signing_key_resolver = signing_key_resolver
        self._monotonic = monotonic

    def authorization_url(
        self,
        *,
        intent: str,
        state: str,
        nonce: str,
        pkce_verifier: str,
    ) -> str:
        if intent not in {"login", "signup"}:
            raise ValueError("unsupported Web authentication intent")
        _validate_browser_value(state)
        _validate_browser_value(nonce)
        _validate_pkce_verifier(pkce_verifier)

        parameters = {
            "response_type": "code",
            "client_id": self._settings.web_client_id,
            "redirect_uri": self._settings.web_callback_url,
            "scope": WEB_SCOPE,
            "state": state,
            "nonce": nonce,
            "code_challenge": _pkce_challenge(pkce_verifier),
            "code_challenge_method": "S256",
        }
        if intent == "login":
            parameters["prompt"] = "login"
        else:
            parameters["screen_hint"] = "signup"
        return f"{self._settings.authorize_url}?{urlencode(parameters)}"

    def exchange_code(
        self,
        *,
        code: str,
        pkce_verifier: str,
        expected_nonce_hash: bytes,
    ) -> VerifiedProviderIdentity:
        try:
            _validate_authorization_code(code)
            _validate_pkce_verifier(pkce_verifier)
        except ValueError:
            raise WebProviderRejectedError from None
        if type(expected_nonce_hash) is not bytes or len(expected_nonce_hash) != 32:
            raise InvalidIdTokenError

        raw_id_token = self._exchange_code_for_id_token(
            code=code,
            pkce_verifier=pkce_verifier,
        )
        return self._verify_id_token(raw_id_token, expected_nonce_hash)

    def _exchange_code_for_id_token(self, *, code: str, pkce_verifier: str) -> str:
        form = {
            "grant_type": "authorization_code",
            "client_id": self._settings.web_client_id,
            "client_secret": self._settings.web_client_secret,
            "code": code,
            "redirect_uri": self._settings.web_callback_url,
            "code_verifier": pkce_verifier,
        }
        try:
            deadline = self._monotonic() + self._settings.jwks_timeout_seconds
            body = bytearray()
            with self._http_client.stream(
                "POST",
                self._settings.token_url,
                data=form,
                headers={"Accept": "application/json", "Accept-Encoding": "identity"},
                follow_redirects=False,
                timeout=self._settings.jwks_timeout_seconds,
            ) as response:
                if self._monotonic() >= deadline:
                    raise WebProviderUnavailableError
                if response.status_code != 200:
                    if 500 <= response.status_code <= 599:
                        raise WebProviderUnavailableError
                    raise IdentityProviderResponseError
                content_encoding = response.headers.get("Content-Encoding")
                if content_encoding is not None and content_encoding.strip().lower() not in {
                    "",
                    "identity",
                }:
                    raise IdentityProviderResponseError
                for chunk in response.iter_bytes():
                    if self._monotonic() >= deadline:
                        raise WebProviderUnavailableError
                    if len(body) + len(chunk) > MAX_TOKEN_RESPONSE_BYTES:
                        raise IdentityProviderResponseError
                    body.extend(chunk)
        except (IdentityProviderResponseError, WebProviderUnavailableError):
            raise
        except httpx2.DecodingError:
            raise IdentityProviderResponseError from None
        except httpx2.HTTPError:
            raise WebProviderUnavailableError from None

        try:
            document = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError, RecursionError):
            raise IdentityProviderResponseError from None
        if not isinstance(document, dict):
            raise IdentityProviderResponseError
        raw_id_token = document.get("id_token")
        if not isinstance(raw_id_token, str) or not raw_id_token:
            raise IdentityProviderResponseError
        return raw_id_token

    def _verify_id_token(
        self,
        raw_id_token: str,
        expected_nonce_hash: bytes,
    ) -> VerifiedProviderIdentity:
        try:
            key_id = read_signing_key_id(raw_id_token)
            signing_key = self._signing_key_resolver.resolve(key_id)
        except (InvalidTokenHeaderError, UnknownSigningKeyError):
            raise InvalidIdTokenError from None
        except JwksUnavailableError:
            raise WebProviderUnavailableError from None

        try:
            decoded = jwt.decode_complete(
                raw_id_token,
                key=signing_key,
                algorithms=[ALGORITHM],
                issuer=self._settings.issuer,
                audience=self._settings.web_client_id,
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
                        "nonce",
                        "email",
                    ],
                    "strict_aud": False,
                    "enforce_minimum_key_length": True,
                },
            )
            payload = decoded["payload"]
            if not isinstance(payload, dict):
                raise InvalidIdTokenError
            return self._to_verified_identity(payload, expected_nonce_hash)
        except WebProviderEmailVerificationRequiredError:
            raise
        except InvalidIdTokenError:
            raise
        except (
            jwt.PyJWTError,
            KeyError,
            OSError,
            OverflowError,
            RecursionError,
            TypeError,
            ValueError,
        ):
            raise InvalidIdTokenError from None

    def _to_verified_identity(
        self,
        payload: dict[str, object],
        expected_nonce_hash: bytes,
    ) -> VerifiedProviderIdentity:
        for claim_name in ("exp", "iat"):
            if type(payload.get(claim_name)) is not int:
                raise InvalidIdTokenError
        if "nbf" in payload and type(payload["nbf"]) is not int:
            raise InvalidIdTokenError

        subject = payload.get("sub")
        audience = payload.get("aud")
        authorized_party = payload.get("azp")
        nonce = payload.get("nonce")
        verified_email = payload.get("email")
        email_verified = payload.get("email_verified")
        if not isinstance(subject, str) or not subject.strip():
            raise InvalidIdTokenError
        if (
            isinstance(audience, list)
            and len(audience) > 1
            and authorized_party != self._settings.web_client_id
        ):
            raise InvalidIdTokenError
        if authorized_party is not None and authorized_party != self._settings.web_client_id:
            raise InvalidIdTokenError
        if not isinstance(nonce, str) or not nonce:
            raise InvalidIdTokenError
        try:
            nonce_hash = hashlib.sha256(nonce.encode("ascii")).digest()
        except UnicodeEncodeError:
            raise InvalidIdTokenError from None
        if not hmac.compare_digest(nonce_hash, expected_nonce_hash):
            raise InvalidIdTokenError
        if not isinstance(verified_email, str) or not verified_email.strip():
            raise InvalidIdTokenError
        if len(verified_email.strip()) > 254:
            raise InvalidIdTokenError
        if email_verified is not True:
            raise WebProviderEmailVerificationRequiredError

        authentication_time: datetime | None = None
        if "auth_time" in payload:
            raw_authentication_time = payload["auth_time"]
            issued_at = payload["iat"]
            if (
                type(raw_authentication_time) is not int
                or type(issued_at) is not int
                or raw_authentication_time > issued_at + self._settings.clock_skew_seconds
            ):
                raise InvalidIdTokenError
            authentication_time = datetime.fromtimestamp(raw_authentication_time, UTC)

        return VerifiedProviderIdentity(
            issuer=self._settings.issuer,
            subject=subject,
            verified_email=verified_email,
            authorized_party=self._settings.web_client_id,
            authentication_time=authentication_time,
        )


def _pkce_challenge(pkce_verifier: str) -> str:
    digest = hashlib.sha256(pkce_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _validate_pkce_verifier(pkce_verifier: str) -> None:
    if type(pkce_verifier) is not str or PKCE_VERIFIER_PATTERN.fullmatch(pkce_verifier) is None:
        raise ValueError("invalid PKCE verifier")


def _validate_browser_value(value: str) -> None:
    if type(value) is not str or not value or len(value) > 1_024:
        raise ValueError("invalid browser authentication value")
    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError("invalid browser authentication value") from None


def _validate_authorization_code(code: str) -> None:
    if type(code) is not str or not code or len(code) > 4_096:
        raise ValueError("invalid authorization code")
    try:
        code.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError("invalid authorization code") from None
