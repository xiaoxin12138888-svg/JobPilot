// @vitest-environment node

import { describe, expect, it } from 'vitest';

import { validateWebEnvironment } from './vite.config';

describe('validateWebEnvironment', () => {
  it('rejects a missing API base URL before Web build or startup', () => {
    expect(() => validateWebEnvironment({})).toThrow('API base URL must be a valid absolute URL');
  });

  it('accepts a valid public HTTP API base URL', () => {
    expect(() =>
      validateWebEnvironment({ VITE_API_BASE_URL: 'http://localhost:8000' }),
    ).not.toThrow();
  });
});
