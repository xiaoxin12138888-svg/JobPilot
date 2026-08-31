import { describe, expect, it } from 'vitest';

import { DEFAULT_API_BASE_URL, loadExtensionConfig } from './config';

describe('loadExtensionConfig', () => {
  it('defaults to the one supported local JobPilot API origin', () => {
    expect(loadExtensionConfig({})).toEqual({ apiBaseUrl: 'http://127.0.0.1:8000' });
    expect(DEFAULT_API_BASE_URL).toBe('http://127.0.0.1:8000');
  });

  it('accepts only the exact supported build-time override', () => {
    expect(loadExtensionConfig({ VITE_API_BASE_URL: 'http://127.0.0.1:8000' })).toEqual({
      apiBaseUrl: 'http://127.0.0.1:8000',
    });
  });

  it.each([
    '',
    ' http://127.0.0.1:8000',
    'http://127.0.0.1:8000 ',
    'http://127.0.0.1:8000/',
    'http://127.0.0.1:8000/health',
    'http://127.0.0.1:8000?mode=remote',
    'http://user:secret@127.0.0.1:8000',
    'https://127.0.0.1:8000',
    'http://localhost:8000',
    'http://[::1]:8000',
    'http://127.0.0.1:8001',
    'http://192.168.1.20:8000',
    'https://api.jobpilot.example.invalid',
  ])('rejects every non-exact API base URL: %s', (apiBaseUrl) => {
    expect(() => loadExtensionConfig({ VITE_API_BASE_URL: apiBaseUrl })).toThrow(
      'VITE_API_BASE_URL must be exactly http://127.0.0.1:8000',
    );
  });
});
