import {
  None,
  customFetch,
  processRefreshTokenResponse,
  processRevocationResponse,
  refreshTokenGrantRequest,
  revocationRequest,
  type AuthorizationServer,
  type Client,
} from 'oauth4webapi';

import type { ExtensionAuthConfig } from './config';
import { ExtensionAuthError } from './errors';
import type { ExchangedProviderCredentials } from './provider-protocol';

const MAX_ACCESS_TOKEN_LIFETIME_SECONDS = 600;
const MAX_CREDENTIAL_LENGTH = 16_384;

interface ProviderRefreshOptions {
  config: ExtensionAuthConfig;
  fetch?: typeof globalThis.fetch;
  now?: number;
  refreshToken: string;
}

interface ProviderRevocationOptions {
  config: ExtensionAuthConfig;
  fetch?: typeof globalThis.fetch;
  refreshToken: string;
}

export async function refreshProviderCredentials(
  options: ProviderRefreshOptions,
): Promise<ExchangedProviderCredentials> {
  try {
    return await refreshProviderCredentialsUnsafe(options);
  } catch {
    throw new ExtensionAuthError('AUTH_REFRESH_FAILED');
  }
}

export async function revokeProviderRefreshGrant(
  options: ProviderRevocationOptions,
): Promise<void> {
  try {
    if (!isBoundedCredential(options.refreshToken)) {
      throw new Error('Invalid refresh credential');
    }
    const response = await revocationRequest(
      authorizationServer(options.config),
      publicClient(options.config),
      None(),
      options.refreshToken,
      {
        additionalParameters: { token_type_hint: 'refresh_token' },
        [customFetch]: createCredentialFreeFetch(options.fetch ?? globalThis.fetch),
      },
    );
    await processRevocationResponse(response);
  } catch {
    throw new ExtensionAuthError('AUTH_PROVIDER_ERROR');
  }
}

async function refreshProviderCredentialsUnsafe(
  options: ProviderRefreshOptions,
): Promise<ExchangedProviderCredentials> {
  if (!isBoundedCredential(options.refreshToken)) {
    throw new Error('Invalid refresh credential');
  }
  const server = authorizationServer(options.config);
  const client = publicClient(options.config);
  const response = await refreshTokenGrantRequest(server, client, None(), options.refreshToken, {
    [customFetch]: createCredentialFreeFetch(options.fetch ?? globalThis.fetch),
  });
  const responseReceivedAt = options.now ?? Date.now();
  if (!isSafeTimestamp(responseReceivedAt)) {
    throw new Error('Invalid token response time');
  }
  await requireNumericExpiresIn(response.clone());

  const tokens = await processRefreshTokenResponse(server, client, response);
  if (
    tokens.token_type !== 'bearer' ||
    !isBoundedCredential(tokens.access_token) ||
    !isBoundedCredential(tokens.refresh_token) ||
    tokens.refresh_token === options.refreshToken ||
    !isBoundedLifetime(tokens.expires_in)
  ) {
    throw new Error('Invalid refresh response');
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

function authorizationServer(config: ExtensionAuthConfig): AuthorizationServer {
  return {
    issuer: config.issuer,
    token_endpoint: config.tokenEndpoint,
    revocation_endpoint: config.revocationEndpoint,
  };
}

function publicClient(config: ExtensionAuthConfig): Client {
  return { client_id: config.clientId };
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

function isBoundedLifetime(value: unknown): value is number {
  return (
    typeof value === 'number' &&
    Number.isSafeInteger(value) &&
    value >= 1 &&
    value <= MAX_ACCESS_TOKEN_LIFETIME_SECONDS
  );
}

function isSafeTimestamp(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
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
