import { describe, expect, it } from 'vitest';

import { createManifest } from './manifest';

const config = { apiBaseUrl: 'http://127.0.0.1:8000' } as const;

describe('createManifest', () => {
  it('exposes only the local Popup and exact loopback health origin', () => {
    expect(createManifest(config)).toEqual({
      manifest_version: 3,
      name: 'JobPilot Extension',
      description: 'Check whether the local JobPilot service is available',
      version: '0.1.0',
      minimum_chrome_version: '106',
      action: {
        default_popup: 'popup.html',
        default_title: 'Check local JobPilot',
      },
      host_permissions: ['http://127.0.0.1:8000/*'],
      content_security_policy: {
        extension_pages:
          "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; connect-src http://127.0.0.1:8000; base-uri 'none'",
      },
    });
  });

  it('has no privileged, background, injected, or OAuth surfaces', () => {
    const manifest = createManifest(config);

    for (const forbiddenKey of [
      'permissions',
      'optional_permissions',
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
