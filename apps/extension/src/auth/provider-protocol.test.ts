// @vitest-environment node

import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ExtensionAuthConfig } from './config';
import { ExtensionAuthError } from './errors';
import { validateAuthorizationCallback, type AuthorizationAttempt } from './authorization';
import { exchangeAuthorizationCode } from './provider-protocol';

const authConfig: ExtensionAuthConfig = {
  issuer: 'https://tenant.example.invalid/',
  authorizationEndpoint: 'https://tenant.example.invalid/authorize',
  tokenEndpoint: 'https://tenant.example.invalid/oauth/token',
  jwksUri: 'https://tenant.example.invalid/.well-known/jwks.json',
  revocationEndpoint: 'https://tenant.example.invalid/oauth/revoke',
  audience: 'https://api.jobpilot.example.invalid',
  clientId: 'public-extension-client-id',
};
const redirectUri = 'https://abcdefghijklmnopabcdefghijklmnop.chromiumapp.org/';
const state = 's'.repeat(43);
const nonce = 'n'.repeat(43);
const codeVerifier = 'v'.repeat(64);
const now = 1_800_000_000_000;
const nowSeconds = now / 1_000;
const signingKeyId = 'jobpilot-test-rs256';

interface IdTokenClaims {
  iss: string;
  sub: string;
  aud: string | string[];
  iat: number;
  exp: number;
  nonce: string;
  nbf?: number;
}

interface CapturedRequest {
  url: string;
  method: string;
  credentials: RequestCredentials | undefined;
  headers: Headers;
  parameters: URLSearchParams;
}

interface ProviderFixtureOptions {
  claims?: Partial<IdTokenClaims>;
  signingKey?: CryptoKey;
  tokenBody?: Record<string, unknown>;
  tokenStatus?: number;
  tokenFailure?: Error;
}

interface ProviderFixture {
  fetch: typeof globalThis.fetch;
  tokenRequest: CapturedRequest | undefined;
  jwksRequest: CapturedRequest | undefined;
}

let trustedKeyPair: CryptoKeyPair;
let untrustedKeyPair: CryptoKeyPair;
let trustedPublicJwk: JsonWebKey;

beforeAll(async () => {
  trustedKeyPair = await generateRs256KeyPair();
  untrustedKeyPair = await generateRs256KeyPair();
  trustedPublicJwk = await crypto.subtle.exportKey('jwk', trustedKeyPair.publicKey);
});

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(now);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('exchangeAuthorizationCode', () => {
  it('validates the signed OIDC response and returns only bounded credentials', async () => {
    const provider = await createProviderFixture();

    const credentials = await exchange(provider);

    expect(credentials).toEqual({
      accessToken: 'access-token-value',
      accessTokenExpiresAt: now + 300_000,
      refreshToken: 'replacement-refresh-token',
    });
    expect(Object.keys(credentials).sort()).toEqual([
      'accessToken',
      'accessTokenExpiresAt',
      'refreshToken',
    ]);
  });

  it('uses public-client none authentication with the exact code and PKCE verifier', async () => {
    const provider = await createProviderFixture();

    await exchange(provider);

    expect(provider.tokenRequest).toBeDefined();
    expect(provider.tokenRequest?.url).toBe(authConfig.tokenEndpoint);
    expect(provider.tokenRequest?.method).toBe('POST');
    expect(provider.tokenRequest?.credentials).toBe('omit');
    expect(provider.tokenRequest?.headers.get('authorization')).toBeNull();
    expect(Object.fromEntries(provider.tokenRequest?.parameters ?? [])).toEqual({
      client_id: authConfig.clientId,
      code: 'authorization-code',
      code_verifier: codeVerifier,
      grant_type: 'authorization_code',
      redirect_uri: redirectUri,
    });
    expect(provider.tokenRequest?.parameters.has('client_secret')).toBe(false);
    expect(provider.tokenRequest?.parameters.has('client_assertion')).toBe(false);
    expect(provider.jwksRequest?.url).toBe(authConfig.jwksUri);
    expect(provider.jwksRequest?.credentials).toBe('omit');
  });

  it.each([
    ['missing access token', { access_token: undefined }],
    ['blank access token', { access_token: '   ' }],
    ['non-bearer token type', { token_type: 'DPoP' }],
    ['missing expiry', { expires_in: undefined }],
    ['zero expiry', { expires_in: 0 }],
    ['fractional expiry', { expires_in: 1.5 }],
    ['expiry above 10 minutes', { expires_in: 601 }],
    ['missing replacement refresh token', { refresh_token: undefined }],
    ['blank replacement refresh token', { refresh_token: '' }],
    ['missing ID token', { id_token: undefined }],
  ])('fails closed for %s', async (_caseName, tokenBody) => {
    const provider = await createProviderFixture({ tokenBody });

    await expect(exchange(provider)).rejects.toMatchObject({
      name: 'ExtensionAuthError',
      code: 'AUTH_TOKEN_EXCHANGE_FAILED',
      message: 'AUTH_TOKEN_EXCHANGE_FAILED',
    });
  });

  it.each([
    ['wrong signature', {}, 'untrusted'],
    ['wrong issuer', { iss: 'https://attacker.example.invalid/' }, 'trusted'],
    ['wrong audience', { aud: 'different-public-client' }, 'trusted'],
    ['wrong nonce', { nonce: 'different-nonce' }, 'trusted'],
    ['expired token', { exp: nowSeconds - 61 }, 'trusted'],
    ['future not-before', { nbf: nowSeconds + 61 }, 'trusted'],
    ['future issued-at', { iat: nowSeconds + 61 }, 'trusted'],
  ] as const)('rejects an ID token with %s', async (_caseName, claims, signer) => {
    const provider = await createProviderFixture({
      claims,
      signingKey: signer === 'trusted' ? trustedKeyPair.privateKey : untrustedKeyPair.privateKey,
    });

    await expect(exchange(provider)).rejects.toMatchObject({
      name: 'ExtensionAuthError',
      code: 'AUTH_TOKEN_EXCHANGE_FAILED',
      message: 'AUTH_TOKEN_EXCHANGE_FAILED',
    });
  });

  it.each(['transport', 'provider'] as const)(
    'sanitizes %s failures without exposing provider details or credentials',
    async (failureKind) => {
      const sensitiveMarker = 'provider-secret-diagnostic';
      const provider = await createProviderFixture(
        failureKind === 'transport'
          ? { tokenFailure: new Error(sensitiveMarker) }
          : {
              tokenStatus: 400,
              tokenBody: {
                error: 'invalid_grant',
                error_description: sensitiveMarker,
              },
            },
      );

      const error: unknown = await exchange(provider).then(
        () => undefined,
        (reason: unknown) => reason,
      );

      expect(error).toBeInstanceOf(ExtensionAuthError);
      expect(error).toMatchObject({
        code: 'AUTH_TOKEN_EXCHANGE_FAILED',
        message: 'AUTH_TOKEN_EXCHANGE_FAILED',
      });
      expect(String(error)).not.toContain(sensitiveMarker);
      expect(JSON.stringify(error)).not.toContain(sensitiveMarker);
      expect(JSON.stringify(error)).not.toContain('authorization-code');
      expect(JSON.stringify(error)).not.toContain(codeVerifier);
    },
  );
});

async function exchange(provider: ProviderFixture) {
  return exchangeAuthorizationCode({
    config: authConfig,
    callback: validatedCallback(),
    fetch: provider.fetch,
    now,
  });
}

function validatedCallback() {
  const attempt: AuthorizationAttempt = {
    version: 1,
    state,
    nonce,
    codeVerifier,
    redirectUri,
    createdAt: now - 1_000,
    expiresAt: now + 599_000,
  };
  const callback = `${redirectUri}?code=authorization-code&state=${state}&iss=${encodeURIComponent(
    authConfig.issuer,
  )}`;
  return validateAuthorizationCallback(callback, attempt, authConfig, now);
}

async function createProviderFixture(
  options: ProviderFixtureOptions = {},
): Promise<ProviderFixture> {
  const claims: IdTokenClaims = {
    iss: authConfig.issuer,
    sub: 'provider-user-id',
    aud: authConfig.clientId,
    iat: nowSeconds - 1,
    exp: nowSeconds + 300,
    nonce,
    ...options.claims,
  };
  const idToken = await signIdToken(claims, options.signingKey ?? trustedKeyPair.privateKey);
  const responseBody: Record<string, unknown> = {
    access_token: 'access-token-value',
    token_type: 'Bearer',
    expires_in: 300,
    refresh_token: 'replacement-refresh-token',
    id_token: idToken,
    ignored_provider_field: 'must-not-cross-the-boundary',
    ...options.tokenBody,
  };
  const fixture: ProviderFixture = {
    fetch: undefined as unknown as typeof globalThis.fetch,
    tokenRequest: undefined,
    jwksRequest: undefined,
  };

  fixture.fetch = async (input, init) => {
    const url = requestUrl(input);
    if (url === authConfig.tokenEndpoint) {
      fixture.tokenRequest = {
        url,
        method: init?.method ?? 'GET',
        credentials: init?.credentials,
        headers: new Headers(init?.headers),
        parameters: formParameters(init?.body),
      };
      if (options.tokenFailure) {
        throw options.tokenFailure;
      }
      return jsonResponse(responseBody, options.tokenStatus ?? 200);
    }
    if (url === authConfig.jwksUri) {
      fixture.jwksRequest = {
        url,
        method: init?.method ?? 'GET',
        credentials: init?.credentials,
        headers: new Headers(init?.headers),
        parameters: formParameters(init?.body),
      };
      return jsonResponse({
        keys: [
          {
            ...trustedPublicJwk,
            alg: 'RS256',
            kid: signingKeyId,
            use: 'sig',
          },
        ],
      });
    }
    throw new Error('Unexpected fake provider request');
  };
  return fixture;
}

async function generateRs256KeyPair(): Promise<CryptoKeyPair> {
  return crypto.subtle.generateKey(
    {
      name: 'RSASSA-PKCS1-v1_5',
      modulusLength: 2_048,
      publicExponent: new Uint8Array([1, 0, 1]),
      hash: 'SHA-256',
    },
    true,
    ['sign', 'verify'],
  );
}

async function signIdToken(claims: IdTokenClaims, privateKey: CryptoKey): Promise<string> {
  const header = base64UrlJson({ alg: 'RS256', kid: signingKeyId, typ: 'JWT' });
  const payload = base64UrlJson(claims);
  const signingInput = `${header}.${payload}`;
  const signature = await crypto.subtle.sign(
    'RSASSA-PKCS1-v1_5',
    privateKey,
    new TextEncoder().encode(signingInput),
  );
  return `${signingInput}.${base64UrlBytes(new Uint8Array(signature))}`;
}

function base64UrlJson(value: unknown): string {
  return base64UrlBytes(new TextEncoder().encode(JSON.stringify(value)));
}

function base64UrlBytes(bytes: Uint8Array): string {
  let binary = '';
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/u, '');
}

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

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'cache-control': 'no-store',
      'content-type': 'application/json',
    },
  });
}
