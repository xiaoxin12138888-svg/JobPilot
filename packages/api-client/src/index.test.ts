import { describe, expect, it, vi } from 'vitest';

import { createApiClient } from './index';

const healthyPayload = {
  status: 'ok',
  service: 'jobpilot-api',
} as const;

describe('createApiClient', () => {
  it('gets and validates the API health response', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(healthyPayload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const client = createApiClient({
      baseUrl: 'http://localhost:8000/base-path',
      fetchImplementation,
    });

    await expect(client.getHealth()).resolves.toEqual(healthyPayload);
    expect(fetchImplementation).toHaveBeenCalledWith('http://localhost:8000/health', {
      headers: { Accept: 'application/json' },
    });
  });

  it('rejects a non-success HTTP response', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(null, { status: 503 }));
    const client = createApiClient({ baseUrl: 'http://localhost:8000', fetchImplementation });

    await expect(client.getHealth()).rejects.toThrow('health request failed with status 503');
  });

  it('rejects an untrusted response with the wrong shape', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify({ status: 'unknown' }), { status: 200 }));
    const client = createApiClient({ baseUrl: 'http://localhost:8000', fetchImplementation });

    await expect(client.getHealth()).rejects.toThrow('invalid health response');
  });

  it('rejects a non-HTTP API base URL', () => {
    expect(() => createApiClient({ baseUrl: 'file:///tmp/jobpilot' })).toThrow(
      'API base URL must use HTTP or HTTPS',
    );
  });

  it('rejects credentials in the public API base URL', () => {
    expect(() => createApiClient({ baseUrl: 'https://user:secret@example.com' })).toThrow(
      'API base URL must not include credentials',
    );
  });
});
