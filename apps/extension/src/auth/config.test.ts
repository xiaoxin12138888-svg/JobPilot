import { describe, expect, it } from 'vitest';

import { loadExtensionConfig } from './config';

const validEnvironment = {
  VITE_API_BASE_URL: 'http://localhost:8000/base',
  VITE_AUTH_ISSUER: 'https://tenant.example.invalid/',
  VITE_AUTH_AUTHORIZE_URL: 'https://tenant.example.invalid/authorize',
  VITE_AUTH_TOKEN_URL: 'https://tenant.example.invalid/oauth/token',
  VITE_AUTH_JWKS_URL: 'https://tenant.example.invalid/.well-known/jwks.json',
  VITE_AUTH_REVOKE_URL: 'https://tenant.example.invalid/oauth/revoke',
  VITE_AUTH_AUDIENCE: 'https://api.jobpilot.example.invalid',
  VITE_AUTH_EXTENSION_CLIENT_ID: 'public-extension-client-id',
  VITE_WEB_APP_URL: 'http://localhost:5173',
};

describe('loadExtensionConfig', () => {
  it('returns one validated public-client configuration', () => {
    const config = loadExtensionConfig(validEnvironment);

    expect(config).toEqual({
      apiBaseUrl: 'http://localhost:8000/base',
      auth: {
        issuer: 'https://tenant.example.invalid/',
        authorizationEndpoint: 'https://tenant.example.invalid/authorize',
        tokenEndpoint: 'https://tenant.example.invalid/oauth/token',
        jwksUri: 'https://tenant.example.invalid/.well-known/jwks.json',
        revocationEndpoint: 'https://tenant.example.invalid/oauth/revoke',
        audience: 'https://api.jobpilot.example.invalid',
        clientId: 'public-extension-client-id',
      },
      webAppUrl: 'http://localhost:5173/',
    });
    expect(config.auth).not.toHaveProperty('clientSecret');
  });

  it.each([
    'VITE_API_BASE_URL',
    'VITE_AUTH_ISSUER',
    'VITE_AUTH_AUTHORIZE_URL',
    'VITE_AUTH_TOKEN_URL',
    'VITE_AUTH_JWKS_URL',
    'VITE_AUTH_REVOKE_URL',
    'VITE_AUTH_AUDIENCE',
    'VITE_AUTH_EXTENSION_CLIENT_ID',
    'VITE_WEB_APP_URL',
  ])('fails fast when %s is absent', (missingKey) => {
    expect(() =>
      loadExtensionConfig({
        ...validEnvironment,
        [missingKey]: undefined,
      }),
    ).toThrow(`Missing Extension configuration: ${missingKey}`);
  });

  it('requires a canonical HTTPS issuer with a trailing slash', () => {
    expect(() =>
      loadExtensionConfig({
        ...validEnvironment,
        VITE_AUTH_ISSUER: 'https://tenant.example.invalid',
      }),
    ).toThrow('VITE_AUTH_ISSUER must use its canonical trailing slash');
  });

  it('rejects a provider endpoint outside the issuer origin', () => {
    expect(() =>
      loadExtensionConfig({
        ...validEnvironment,
        VITE_AUTH_TOKEN_URL: 'https://attacker.example.invalid/oauth/token',
      }),
    ).toThrow('VITE_AUTH_TOKEN_URL must share the issuer origin');
  });

  it('rejects credentials and suffixes in fixed provider endpoints', () => {
    expect(() =>
      loadExtensionConfig({
        ...validEnvironment,
        VITE_AUTH_REVOKE_URL: 'https://user:secret@tenant.example.invalid/oauth/revoke?x=1',
      }),
    ).toThrow('VITE_AUTH_REVOKE_URL must be a fixed HTTPS URL');
  });

  it('rejects a Web application URL that is not an exact HTTP origin', () => {
    expect(() =>
      loadExtensionConfig({
        ...validEnvironment,
        VITE_WEB_APP_URL: 'https://jobpilot.example.invalid/dashboard?token=no',
      }),
    ).toThrow('VITE_WEB_APP_URL must be an exact HTTP or HTTPS origin');
  });
});
