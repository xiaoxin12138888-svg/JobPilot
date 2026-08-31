import {
  None,
  authorizationCodeGrantRequest,
  clockTolerance,
  customFetch,
  getValidatedIdTokenClaims,
  processAuthorizationCodeResponse,
  validateApplicationLevelSignature,
  validateAuthResponse,
  type AuthorizationServer,
  type Client,
} from 'oauth4webapi';

import type { ValidatedAuthorizationCallback } from './authorization';
import type { ExtensionAuthConfig } from './config';
import { ExtensionAuthError } from './errors';

const CLOCK_TOLERANCE_SECONDS = 30;
const MAX_ACCESS_TOKEN_LIFETIME_SECONDS = 600;
const MAX_CREDENTIAL_LENGTH = 16_384;

export interface ExchangedProviderCredentials {
  accessToken: string;
  accessTokenExpiresAt: number;
  refreshToken: string;
}

interface ExchangeAuthorizationCodeOptions {
  config: ExtensionAuthConfig;
  callback: ValidatedAuthorizationCallback;
  fetch?: typeof globalThis.fetch;
  now?: number;
}

export async function exchangeAuthorizationCode(
  options: ExchangeAuthorizationCodeOptions,
): Promise<ExchangedProviderCredentials> {
  try {
    return await exchangeAuthorizationCodeUnsafe(options);
  } catch {
    throw new ExtensionAuthError('AUTH_TOKEN_EXCHANGE_FAILED');
  }
}

async function exchangeAuthorizationCodeUnsafe(
  options: ExchangeAuthorizationCodeOptions,
): Promise<ExchangedProviderCredentials> {
  const authorizationServer: AuthorizationServer = {
    issuer: options.config.issuer,
    token_endpoint: options.config.tokenEndpoint,
    jwks_uri: options.config.jwksUri,
    id_token_signing_alg_values_supported: ['RS256'],
  };
  const client: Client = {
    client_id: options.config.clientId,
    id_token_signed_response_alg: 'RS256',
    [clockTolerance]: CLOCK_TOLERANCE_SECONDS,
  };
  const fetchImplementation = options.fetch ?? globalThis.fetch;
  const providerFetch = createCredentialFreeFetch(fetchImplementation);
  const callbackParameters = validateAuthResponse(
    authorizationServer,
    client,
    options.callback.parameters,
    options.callback.attempt.state,
  );

  const response = await authorizationCodeGrantRequest(
    authorizationServer,
    client,
    None(),
    callbackParameters,
    options.callback.attempt.redirectUri,
    options.callback.attempt.codeVerifier,
    { [customFetch]: providerFetch },
  );
  const responseReceivedAt = options.now ?? Date.now();
  if (!Number.isSafeInteger(responseReceivedAt)) {
    throw new Error('Invalid token response time');
  }
  await requireNumericExpiresIn(response.clone());

  const tokens = await processAuthorizationCodeResponse(authorizationServer, client, response, {
    expectedNonce: options.callback.attempt.nonce,
    requireIdToken: true,
  });
  await validateApplicationLevelSignature(authorizationServer, response, {
    [customFetch]: providerFetch,
  });

  const claims = getValidatedIdTokenClaims(tokens);
  const claimsCheckedAt = options.now ?? Date.now();
  if (!hasValidIdTokenTimes(claims, claimsCheckedAt)) {
    throw new Error('Invalid ID token time claims');
  }
  if (
    tokens.token_type !== 'bearer' ||
    !isBoundedCredential(tokens.access_token) ||
    !isBoundedCredential(tokens.refresh_token) ||
    !isBoundedCredential(tokens.id_token) ||
    !isBoundedLifetime(tokens.expires_in)
  ) {
    throw new Error('Invalid token response');
  }

  const accessTokenExpiresAt = responseReceivedAt + tokens.expires_in * 1_000;
  if (!Number.isSafeInteger(accessTokenExpiresAt)) {
    throw new Error('Invalid access token expiry');
  }
  return {
    accessToken: tokens.access_token,
    accessTokenExpiresAt,
    refreshToken: tokens.refresh_token,
  };
}

function createCredentialFreeFetch(fetchImplementation: typeof globalThis.fetch) {
  return (
    url: string,
    options: {
      body: BodyInit | undefined;
      headers: Record<string, string>;
      method: string;
      redirect: 'manual';
      signal?: AbortSignal;
    },
  ): Promise<Response> => {
    const request: RequestInit = {
      body: options.body ?? null,
      credentials: 'omit',
      headers: options.headers,
      method: options.method,
      redirect: options.redirect,
    };
    if (options.signal !== undefined) {
      request.signal = options.signal;
    }
    return fetchImplementation(url, request);
  };
}

async function requireNumericExpiresIn(response: Response): Promise<void> {
  const payload: unknown = await response.json();
  if (
    !isRecord(payload) ||
    typeof payload.expires_in !== 'number' ||
    !isBoundedLifetime(payload.expires_in)
  ) {
    throw new Error('Invalid token response expiry');
  }
}

function hasValidIdTokenTimes(
  claims: ReturnType<typeof getValidatedIdTokenClaims>,
  now: number,
): boolean {
  if (
    claims === undefined ||
    !Number.isSafeInteger(now) ||
    !Number.isSafeInteger(claims.iat) ||
    claims.iat < 0 ||
    !Number.isSafeInteger(claims.exp) ||
    claims.exp <= 0 ||
    claims.iat > claims.exp
  ) {
    return false;
  }
  if (claims.nbf !== undefined && (!Number.isSafeInteger(claims.nbf) || claims.nbf < 0)) {
    return false;
  }
  return claims.iat <= Math.floor(now / 1_000) + CLOCK_TOLERANCE_SECONDS;
}

function isBoundedLifetime(value: unknown): value is number {
  return (
    typeof value === 'number' &&
    Number.isSafeInteger(value) &&
    value >= 1 &&
    value <= MAX_ACCESS_TOKEN_LIFETIME_SECONDS
  );
}

function isBoundedCredential(value: unknown): value is string {
  if (typeof value !== 'string' || value.length === 0 || value.length > MAX_CREDENTIAL_LENGTH) {
    return false;
  }
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code <= 0x20 || code > 0x7e) {
      return false;
    }
  }
  return true;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
