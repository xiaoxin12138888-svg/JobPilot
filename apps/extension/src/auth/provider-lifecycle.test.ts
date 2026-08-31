// @vitest-environment node

import { describe, expect, it, vi } from 'vitest';

import type { ExtensionAuthConfig } from './config';
import { ExtensionAuthError } from './errors';
import { refreshProviderCredentials, revokeProviderRefreshGrant } from './provider-lifecycle';

const now = 1_800_000_000_000;
const oldRefreshToken = 'old-rotating-refresh-token';
const authConfig: ExtensionAuthConfig = {
  issuer: 'https://tenant.example.invalid/',
  authorizationEndpoint: 'https://tenant.example.invalid/authorize',
  tokenEndpoint: 'https://tenant.example.invalid/oauth/token',
  jwksUri: 'https://tenant.example.invalid/.well-known/jwks.json',
  revocationEndpoint: 'https://tenant.example.invalid/oauth/revoke',
  audience: 'https://api.jobpilot.example.invalid',
  clientId: 'public-extension-client-id',
};

interface CapturedRequest {
  credentials: RequestCredentials | undefined;
  headers: Headers;
  method: string;
  parameters: URLSearchParams;
  redirect: RequestRedirect | undefined;
  url: string;
}

interface ProviderFixtureOptions {
  refreshBody?: Record<string, unknown>;
  refreshFailure?: Error;
  refreshStatus?: number;
  revokeBody?: Record<string, unknown>;
  revokeFailure?: Error;
  revokeStatus?: number;
}

function createProviderFixture(options: ProviderFixtureOptions = {}) {
  const requests: CapturedRequest[] = [];
  const fetch = vi.fn<typeof globalThis.fetch>(async (input, init) => {
    const url = requestUrl(input);
    requests.push({
      credentials: init?.credentials,
      headers: new Headers(init?.headers),
      method: init?.method ?? 'GET',
      parameters: formParameters(init?.body),
      redirect: init?.redirect,
      url,
    });

    if (url === authConfig.tokenEndpoint) {
      if (options.refreshFailure) {
        throw options.refreshFailure;
      }
      return jsonResponse(
        {
          access_token: 'replacement-access-token',
          token_type: 'Bearer',
          expires_in: 300,
          refresh_token: 'replacement-refresh-token',
          ignored_provider_field: 'must-not-cross-the-boundary',
          ...options.refreshBody,
        },
        options.refreshStatus ?? 200,
      );
    }
    if (url === authConfig.revocationEndpoint) {
      if (options.revokeFailure) {
        throw options.revokeFailure;
      }
      const status = options.revokeStatus ?? 200;
      return status === 200
        ? new Response(null, { status })
        : jsonResponse(
            {
              error: 'temporarily_unavailable',
              ...options.revokeBody,
            },
            status,
          );
    }
    throw new Error('Unexpected fake provider request');
  });
  return { fetch, requests };
}

describe('refreshProviderCredentials', () => {
  it('uses one public-client refresh request and returns only bounded replacement credentials', async () => {
    const provider = createProviderFixture();

    const result = await refreshProviderCredentials({
      config: authConfig,
      fetch: provider.fetch,
      now,
      refreshToken: oldRefreshToken,
    });

    expect(result).toEqual({
      accessToken: 'replacement-access-token',
      accessTokenExpiresAt: now + 300_000,
      refreshToken: 'replacement-refresh-token',
    });
    expect(Object.keys(result).sort()).toEqual([
      'accessToken',
      'accessTokenExpiresAt',
      'refreshToken',
    ]);
    expect(provider.requests).toHaveLength(1);
    const request = provider.requests[0];
    expect(request).toMatchObject({
      credentials: 'omit',
      method: 'POST',
      redirect: 'manual',
      url: authConfig.tokenEndpoint,
    });
    expect(request?.headers.get('authorization')).toBeNull();
    expect(Object.fromEntries(request?.parameters ?? [])).toEqual({
      client_id: authConfig.clientId,
      grant_type: 'refresh_token',
      refresh_token: oldRefreshToken,
    });
    expect(request?.parameters.has('client_secret')).toBe(false);
    expect(request?.parameters.has('client_assertion')).toBe(false);
  });

  it.each([
    ['missing access token', { access_token: undefined }],
    ['non-bearer token type', { token_type: 'DPoP' }],
    ['missing expiry', { expires_in: undefined }],
    ['fractional expiry', { expires_in: 1.5 }],
    ['expiry above ten minutes', { expires_in: 601 }],
    ['missing replacement refresh token', { refresh_token: undefined }],
    ['unchanged refresh token', { refresh_token: oldRefreshToken }],
    ['credential with a control character', { refresh_token: 'replacement\nrefresh-token' }],
  ])('fails closed for %s', async (_caseName, refreshBody) => {
    const provider = createProviderFixture({ refreshBody });

    await expect(
      refreshProviderCredentials({
        config: authConfig,
        fetch: provider.fetch,
        now,
        refreshToken: oldRefreshToken,
      }),
    ).rejects.toEqual(new ExtensionAuthError('AUTH_REFRESH_FAILED'));
    expect(provider.requests).toHaveLength(1);
  });

  it.each(['transport', 'invalid_grant'] as const)(
    'sanitizes %s failure and never retries',
    async (failureKind) => {
      const sensitiveMarker = 'provider-secret-diagnostic';
      const provider = createProviderFixture(
        failureKind === 'transport'
          ? { refreshFailure: new Error(sensitiveMarker) }
          : {
              refreshBody: {
                error: 'invalid_grant',
                error_description: sensitiveMarker,
              },
              refreshStatus: 400,
            },
      );

      const error: unknown = await refreshProviderCredentials({
        config: authConfig,
        fetch: provider.fetch,
        now,
        refreshToken: oldRefreshToken,
      }).then(
        () => undefined,
        (reason: unknown) => reason,
      );

      expect(error).toEqual(new ExtensionAuthError('AUTH_REFRESH_FAILED'));
      expect(String(error)).not.toContain(sensitiveMarker);
      expect(JSON.stringify(error)).not.toContain(sensitiveMarker);
      expect(JSON.stringify(error)).not.toContain(oldRefreshToken);
      expect(provider.requests).toHaveLength(1);
    },
  );
});

describe('revokeProviderRefreshGrant', () => {
  it('uses one credential-free public-client revocation request', async () => {
    const provider = createProviderFixture();

    await expect(
      revokeProviderRefreshGrant({
        config: authConfig,
        fetch: provider.fetch,
        refreshToken: oldRefreshToken,
      }),
    ).resolves.toBeUndefined();

    expect(provider.requests).toHaveLength(1);
    const request = provider.requests[0];
    expect(request).toMatchObject({
      credentials: 'omit',
      method: 'POST',
      redirect: 'manual',
      url: authConfig.revocationEndpoint,
    });
    expect(request?.headers.get('authorization')).toBeNull();
    expect(Object.fromEntries(request?.parameters ?? [])).toEqual({
      client_id: authConfig.clientId,
      token: oldRefreshToken,
      token_type_hint: 'refresh_token',
    });
    expect(request?.parameters.has('client_secret')).toBe(false);
  });

  it.each(['transport', 'provider'] as const)(
    'sanitizes %s revocation failure and never retries',
    async (failureKind) => {
      const sensitiveMarker = 'provider-secret-diagnostic';
      const provider = createProviderFixture(
        failureKind === 'transport'
          ? { revokeFailure: new Error(sensitiveMarker) }
          : {
              revokeBody: { error_description: sensitiveMarker },
              revokeStatus: 503,
            },
      );

      const error: unknown = await revokeProviderRefreshGrant({
        config: authConfig,
        fetch: provider.fetch,
        refreshToken: oldRefreshToken,
      }).then(
        () => undefined,
        (reason: unknown) => reason,
      );

      expect(error).toEqual(new ExtensionAuthError('AUTH_PROVIDER_ERROR'));
      expect(String(error)).not.toContain(sensitiveMarker);
      expect(JSON.stringify(error)).not.toContain(sensitiveMarker);
      expect(JSON.stringify(error)).not.toContain(oldRefreshToken);
      expect(provider.requests).toHaveLength(1);
    },
  );
});

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') {
    return input;
  }
  return input instanceof URL ? input.toString() : input.url;
}

function formParameters(body: BodyInit | null | undefined): URLSearchParams {
  if (body instanceof URLSearchParams) {
    return new URLSearchParams(body);
  }
  return new URLSearchParams(typeof body === 'string' ? body : '');
}

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'cache-control': 'no-store',
      'content-type': 'application/json',
    },
  });
}
