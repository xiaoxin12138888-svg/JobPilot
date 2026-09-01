// @vitest-environment node

import { describe, expect, it } from 'vitest';

import { createWebConfig, validateWebEnvironment } from './vite.config';

describe('validateWebEnvironment', () => {
  it('uses the exact IPv4 loopback API when no environment override is provided', () => {
    const config = createWebConfig({});

    expect(() => validateWebEnvironment({})).not.toThrow();
    expect(config.define).toEqual({
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://127.0.0.1:8000'),
    });
  });

  it.each(['http://localhost:8000', 'http://127.0.0.1:8000', 'http://[::1]:8000'])(
    'accepts the loopback API base URL %s',
    (baseUrl) => {
      expect(() => validateWebEnvironment({ VITE_API_BASE_URL: baseUrl })).not.toThrow();
    },
  );

  it.each(['https://api.jobpilot.example.com', 'http://192.168.1.10:8000', 'http://0.0.0.0:8000'])(
    'rejects the non-loopback API base URL %s',
    (baseUrl) => {
      expect(() => validateWebEnvironment({ VITE_API_BASE_URL: baseUrl })).toThrow(
        'API base URL must use a loopback host',
      );
    },
  );

  it('pins the Web development server to IPv4 loopback', () => {
    const config = createWebConfig({ VITE_API_BASE_URL: 'http://127.0.0.1:8000' });

    expect(config.server?.host).toBe('127.0.0.1');
  });
});
