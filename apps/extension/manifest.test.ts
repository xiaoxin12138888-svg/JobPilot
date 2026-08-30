import { describe, expect, it } from 'vitest';

import { createManifest } from './manifest';

describe('createManifest', () => {
  it('uses activeTab and only the configured API origin', () => {
    const manifest = createManifest('http://localhost:8000/api');

    expect(manifest.manifest_version).toBe(3);
    expect(manifest.permissions).toEqual(['activeTab']);
    expect(manifest.host_permissions).toEqual(['http://localhost:8000/*']);
    expect(manifest).not.toHaveProperty('background');
    expect(manifest).not.toHaveProperty('content_scripts');
  });

  it('rejects a non-HTTP API origin', () => {
    expect(() => createManifest('file:///tmp/jobpilot')).toThrow(
      'API base URL must use HTTP or HTTPS',
    );
  });

  it('rejects credentials in the public API base URL', () => {
    expect(() => createManifest('https://user:secret@example.com')).toThrow(
      'API base URL must not include credentials',
    );
  });
});
