import { describe, expect, it } from 'vitest';

import { createManifest } from './manifest';

const config = {
  apiBaseUrl: 'http://localhost:8000/api',
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
};

describe('createManifest', () => {
  it('uses only the trusted authentication permissions and exact origins', () => {
    const manifest = createManifest(config);

    expect(manifest.manifest_version).toBe(3);
    expect(manifest.minimum_chrome_version).toBe('106');
    expect(manifest.permissions).toEqual(['identity', 'storage']);
    expect(manifest.host_permissions).toEqual([
      'http://localhost:8000/*',
      'https://tenant.example.invalid/*',
    ]);
    expect(manifest.background).toEqual({
      service_worker: 'background.js',
      type: 'module',
    });
    expect(manifest.content_security_policy).toEqual({
      extension_pages: "script-src 'self'; object-src 'self'",
    });
    expect(manifest).not.toHaveProperty('content_scripts');
  });

  it('deduplicates host permissions when API and provider share an origin', () => {
    expect(
      createManifest({
        ...config,
        apiBaseUrl: 'https://tenant.example.invalid/api',
      }).host_permissions,
    ).toEqual(['https://tenant.example.invalid/*']);
  });
});
