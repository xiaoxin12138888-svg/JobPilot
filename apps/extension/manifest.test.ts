import { describe, expect, it } from 'vitest';

import extensionIdentity from './extension-public-key.json' with { type: 'json' };
import { createManifest } from './manifest';

const config = { apiBaseUrl: 'http://127.0.0.1:8000' } as const;

describe('createManifest', () => {
  it('exposes only user-triggered current-tab capture and the exact loopback API origin', () => {
    expect(createManifest(config)).toEqual({
      manifest_version: 3,
      name: 'JobPilot Extension',
      description: 'Capture the current recruitment job into the local JobPilot workspace',
      version: '0.1.0',
      minimum_chrome_version: '106',
      key: extensionIdentity.publicKey,
      action: {
        default_popup: 'popup.html',
        default_title: 'Capture current recruitment job',
      },
      permissions: ['activeTab', 'scripting'],
      host_permissions: ['http://127.0.0.1:8000/*'],
      content_security_policy: {
        extension_pages:
          "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; connect-src http://127.0.0.1:8000; base-uri 'none'",
      },
    });
  });

  it('has no broad host, persistent injection, background, or OAuth surfaces', () => {
    const manifest = createManifest(config);

    expect(manifest.permissions).toEqual(['activeTab', 'scripting']);
    expect(manifest.host_permissions).toEqual(['http://127.0.0.1:8000/*']);

    for (const forbiddenKey of [
      'optional_permissions',
      'optional_host_permissions',
      'background',
      'content_scripts',
      'oauth2',
      'externally_connectable',
      'web_accessible_resources',
    ]) {
      expect(manifest).not.toHaveProperty(forbiddenKey);
    }
  });
});
