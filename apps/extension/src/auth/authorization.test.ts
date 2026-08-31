// @vitest-environment node

import { describe, expect, it, vi } from 'vitest';

import type { ExtensionAuthConfig } from './config';
import { ExtensionAuthError } from './errors';
import {
  InteractiveAuthorization,
  calculateS256CodeChallenge,
  createAuthorizationRequest,
  createDefaultAuthorizationPrimitives,
  validateAuthorizationCallback,
  type AuthorizationAttempt,
  type AuthorizationPrimitives,
} from './authorization';

const authConfig: ExtensionAuthConfig = {
  issuer: 'https://tenant.example.invalid/',
  authorizationEndpoint: 'https://tenant.example.invalid/authorize',
  tokenEndpoint: 'https://tenant.example.invalid/oauth/token',
  jwksUri: 'https://tenant.example.invalid/.well-known/jwks.json',
  revocationEndpoint: 'https://tenant.example.invalid/oauth/revoke',
  audience: 'https://api.jobpilot.example.invalid',
  clientId: 'public-extension-client-id',
};
const extensionId = 'abcdefghijklmnopabcdefghijklmnop';
const redirectUri = `https://${extensionId}.chromiumapp.org/`;
const stateValue = 's'.repeat(43);
const nonceValue = 'n'.repeat(43);
const now = 1_800_000_000_000;
const issuerParameter = `iss=${encodeURIComponent(authConfig.issuer)}`;

function callbackUrl(parameters: string): string {
  return `${redirectUri}?${parameters}&${issuerParameter}`;
}

const deterministicPrimitives: AuthorizationPrimitives = {
  generateCodeVerifier: () => 'a'.repeat(64),
  generateState: () => stateValue,
  generateNonce: () => nonceValue,
  calculateCodeChallenge: vi.fn().mockResolvedValue('challenge-value'),
};

function attempt(overrides: Partial<AuthorizationAttempt> = {}): AuthorizationAttempt {
  return {
    version: 1,
    state: stateValue,
    nonce: nonceValue,
    codeVerifier: 'a'.repeat(64),
    redirectUri,
    createdAt: now,
    expiresAt: now + 600_000,
    ...overrides,
  };
}

describe('authorization PKCE attempt', () => {
  it('calculates the RFC 7636 S256 example', async () => {
    await expect(
      calculateS256CodeChallenge('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'),
    ).resolves.toBe('E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM');
  });

  it('uses secure OAuth primitives with verifier/state/nonce format boundaries', () => {
    const primitives = createDefaultAuthorizationPrimitives();

    const first = {
      verifier: primitives.generateCodeVerifier(),
      state: primitives.generateState(),
      nonce: primitives.generateNonce(),
    };
    const second = {
      verifier: primitives.generateCodeVerifier(),
      state: primitives.generateState(),
      nonce: primitives.generateNonce(),
    };

    expect(first.verifier).toMatch(/^[A-Za-z0-9._~-]{43,128}$/u);
    expect(first.state).toMatch(/^[A-Za-z0-9._~-]{32,128}$/u);
    expect(first.nonce).toMatch(/^[A-Za-z0-9._~-]{32,128}$/u);
    expect(second).not.toEqual(first);
  });

  it('builds a bounded code-only authorization request with S256 and offline access', async () => {
    const created = await createAuthorizationRequest({
      config: authConfig,
      redirectUri,
      now,
      primitives: deterministicPrimitives,
    });

    expect(created.attempt).toEqual(attempt());
    expect(created.authorizationUrl.origin + created.authorizationUrl.pathname).toBe(
      authConfig.authorizationEndpoint,
    );
    expect(Object.fromEntries(created.authorizationUrl.searchParams)).toEqual({
      audience: authConfig.audience,
      client_id: authConfig.clientId,
      code_challenge: 'challenge-value',
      code_challenge_method: 'S256',
      nonce: nonceValue,
      redirect_uri: redirectUri,
      response_type: 'code',
      scope: 'openid profile email offline_access',
      state: stateValue,
    });
  });
});

describe('validateAuthorizationCallback', () => {
  it('accepts one exact callback with matching state and code', () => {
    const result = validateAuthorizationCallback(
      callbackUrl(`code=authorization-code&state=${stateValue}`),
      attempt(),
      authConfig,
      now + 1,
    );

    expect(result.parameters.get('code')).toBe('authorization-code');
    expect(result.attempt).toEqual(attempt());
  });

  it('accepts an exact callback when the provider omits the optional issuer parameter', () => {
    const result = validateAuthorizationCallback(
      `${redirectUri}?code=authorization-code&state=${stateValue}`,
      attempt(),
      authConfig,
      now + 1,
    );

    expect(result.parameters.get('code')).toBe('authorization-code');
  });

  it.each([
    ['missing state', callbackUrl('code=authorization-code'), 'AUTH_STATE_MISMATCH'],
    [
      'mismatched state',
      callbackUrl(`code=authorization-code&state=${'x'.repeat(43)}`),
      'AUTH_STATE_MISMATCH',
    ],
    ['missing code', callbackUrl(`state=${stateValue}`), 'AUTH_TOKEN_EXCHANGE_FAILED'],
    [
      'provider error',
      callbackUrl(`error=access_denied&error_description=private&state=${stateValue}`),
      'AUTH_PROVIDER_ERROR',
    ],
    [
      'wrong callback origin',
      `https://attacker.example.invalid/?code=authorization-code&state=${stateValue}&${issuerParameter}`,
      'AUTH_STATE_MISMATCH',
    ],
    [
      'fragment response',
      `${redirectUri}#code=authorization-code&state=${stateValue}&${issuerParameter}`,
      'AUTH_STATE_MISMATCH',
    ],
    [
      'duplicate state',
      callbackUrl(`code=authorization-code&state=${stateValue}&state=${stateValue}`),
      'AUTH_STATE_MISMATCH',
    ],
    [
      'mismatched issuer',
      `${redirectUri}?code=authorization-code&state=${stateValue}&iss=${encodeURIComponent('https://attacker.example.invalid/')}`,
      'AUTH_STATE_MISMATCH',
    ],
    [
      'duplicate issuer',
      `${callbackUrl(`code=authorization-code&state=${stateValue}`)}&${issuerParameter}`,
      'AUTH_STATE_MISMATCH',
    ],
    [
      'hybrid ID token',
      callbackUrl(`code=authorization-code&id_token=private&state=${stateValue}`),
      'AUTH_STATE_MISMATCH',
    ],
    [
      'implicit access token',
      callbackUrl(`access_token=private&token_type=Bearer&state=${stateValue}`),
      'AUTH_STATE_MISMATCH',
    ],
  ])('rejects %s without exposing callback values', (_name, callbackUrl, code) => {
    expect(() =>
      validateAuthorizationCallback(callbackUrl, attempt(), authConfig, now + 1),
    ).toThrowError(expect.objectContaining({ code }));
  });

  it('rejects a stale attempt', () => {
    expect(() =>
      validateAuthorizationCallback(
        callbackUrl(`code=authorization-code&state=${stateValue}`),
        attempt(),
        authConfig,
        now + 600_000,
      ),
    ).toThrowError(expect.objectContaining({ code: 'AUTH_ATTEMPT_EXPIRED' }));
  });

  it('rejects an attempt whose creation time is still in the future', () => {
    expect(() =>
      validateAuthorizationCallback(
        callbackUrl(`code=authorization-code&state=${stateValue}`),
        attempt({ createdAt: now + 1, expiresAt: now + 600_001 }),
        authConfig,
        now,
      ),
    ).toThrowError(expect.objectContaining({ code: 'AUTH_ATTEMPT_EXPIRED' }));
  });

  it('rejects an invalid clock reading', () => {
    expect(() =>
      validateAuthorizationCallback(
        callbackUrl(`code=authorization-code&state=${stateValue}`),
        attempt(),
        authConfig,
        Number.NaN,
      ),
    ).toThrowError(expect.objectContaining({ code: 'AUTH_ATTEMPT_EXPIRED' }));
  });
});

describe('InteractiveAuthorization', () => {
  it('launches interactively from the runtime redirect and consumes the stored attempt', async () => {
    const stored = attempt();
    const store = {
      saveAttempt: vi.fn().mockResolvedValue(undefined),
      loadAttempt: vi.fn().mockResolvedValue(stored),
      clearAttempt: vi.fn().mockResolvedValue(undefined),
    };
    const identity = {
      getRedirectURL: vi.fn().mockReturnValue(redirectUri),
      launchWebAuthFlow: vi
        .fn()
        .mockResolvedValue(callbackUrl(`code=authorization-code&state=${stateValue}`)),
    };
    const authorization = new InteractiveAuthorization({
      config: authConfig,
      store,
      identity,
      clock: () => now,
      primitives: deterministicPrimitives,
    });

    const result = await authorization.launch();

    expect(identity.getRedirectURL).toHaveBeenCalledWith();
    expect(identity.launchWebAuthFlow).toHaveBeenCalledWith({
      interactive: true,
      url: expect.stringContaining('code_challenge_method=S256'),
    });
    expect(store.saveAttempt).toHaveBeenCalledWith(stored);
    expect(result.parameters.get('code')).toBe('authorization-code');
    expect(store.clearAttempt).toHaveBeenCalledOnce();
  });

  it.each([
    ['undefined callback', vi.fn().mockResolvedValue(undefined)],
    ['launch rejection', vi.fn().mockRejectedValue(new Error('private Chrome error'))],
  ])('maps %s to cancellation and still clears the attempt', async (_name, launchWebAuthFlow) => {
    const store = {
      saveAttempt: vi.fn().mockResolvedValue(undefined),
      loadAttempt: vi.fn().mockResolvedValue(attempt()),
      clearAttempt: vi.fn().mockResolvedValue(undefined),
    };
    const authorization = new InteractiveAuthorization({
      config: authConfig,
      store,
      identity: { getRedirectURL: () => redirectUri, launchWebAuthFlow },
      clock: () => now,
      primitives: deterministicPrimitives,
    });

    await expect(authorization.launch()).rejects.toEqual(new ExtensionAuthError('AUTH_CANCELLED'));
    expect(store.clearAttempt).toHaveBeenCalledOnce();
  });

  it.each([
    [
      'provider error',
      callbackUrl(`error=access_denied&state=${stateValue}`),
      now + 1,
      'AUTH_PROVIDER_ERROR',
    ],
    [
      'state mismatch',
      callbackUrl(`code=authorization-code&state=${'x'.repeat(43)}`),
      now + 1,
      'AUTH_STATE_MISMATCH',
    ],
    [
      'stale callback',
      callbackUrl(`code=authorization-code&state=${stateValue}`),
      now + 600_000,
      'AUTH_ATTEMPT_EXPIRED',
    ],
  ])('clears the attempt after a %s terminal path', async (_name, callback, completedAt, code) => {
    const store = {
      saveAttempt: vi.fn().mockResolvedValue(undefined),
      loadAttempt: vi.fn().mockResolvedValue(attempt()),
      clearAttempt: vi.fn().mockResolvedValue(undefined),
    };
    const clock = vi.fn().mockReturnValueOnce(now).mockReturnValue(completedAt);
    const authorization = new InteractiveAuthorization({
      config: authConfig,
      store,
      identity: {
        getRedirectURL: () => redirectUri,
        launchWebAuthFlow: vi.fn().mockResolvedValue(callback),
      },
      clock,
      primitives: deterministicPrimitives,
    });

    await expect(authorization.launch()).rejects.toEqual(expect.objectContaining({ code }));
    expect(store.clearAttempt).toHaveBeenCalledOnce();
  });
});
