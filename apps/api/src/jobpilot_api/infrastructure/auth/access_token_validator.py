from __future__ import annotations

import time
from collections.abc import Callable

import httpx2
import jwt

from jobpilot_api.config import AuthSettings
from jobpilot_api.domain.identity import VerifiedProviderIdentity
from jobpilot_api.infrastructure.auth.jwks import (
    ALGORITHM,
    InvalidTokenHeaderError,
    JwksResolver,
    UnknownSigningKeyError,
    read_signing_key_id,
)
from jobpilot_api.infrastructure.auth.jwks import (
    IdentityProviderUnavailableError as IdentityProviderUnavailableError,
)


class InvalidAccessTokenError(Exception):
    """The credential does not satisfy the Extension access-token contract."""


class EmailVerificationRequiredError(Exception):
    """The signed provider identity has not completed email verification."""


class ExtensionAccessTokenValidator:
    """Validate Extension access tokens against a process-scoped JWKS resolver."""

    def __init__(
        self,
        settings: AuthSettings,
        http_client: httpx2.Client,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        signing_key_resolver: JwksResolver | None = None,
    ) -> None:
        self._settings = settings
        self._signing_key_resolver = signing_key_resolver or JwksResolver(
            settings,
            http_client,
            monotonic=monotonic,
        )

    def validate(self, raw_token: str) -> VerifiedProviderIdentity:
        try:
            key_id = read_signing_key_id(raw_token)
            signing_key = self._signing_key_resolver.resolve(key_id)
        except (InvalidTokenHeaderError, UnknownSigningKeyError):
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
