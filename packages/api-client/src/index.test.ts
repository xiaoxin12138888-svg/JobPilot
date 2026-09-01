import { afterEach, describe, expect, it, vi } from 'vitest';

import * as apiClientModule from './index';
import { createApiClient } from './index';

const healthyPayload = {
  status: 'ok',
  service: 'jobpilot-api',
} as const;

afterEach(() => {
  vi.useRealTimers();
});

describe('createApiClient', () => {
  it('exports only the health-only client surface at runtime', () => {
    expect(Object.keys(apiClientModule).sort()).toEqual(['createApiClient', 'validateApiBaseUrl']);
  });

  it('gets and validates the exact API health response without credentials or redirects', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(healthyPayload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const client = createApiClient({
      baseUrl: 'http://127.0.0.1:8000/base-path',
      fetchImplementation,
    });

    await expect(client.getHealth()).resolves.toEqual(healthyPayload);
    expect(fetchImplementation).toHaveBeenCalledOnce();
    expect(fetchImplementation).toHaveBeenCalledWith('http://127.0.0.1:8000/health', {
      cache: 'no-store',
      credentials: 'omit',
      headers: { Accept: 'application/json' },
      method: 'GET',
      redirect: 'error',
      signal: expect.any(AbortSignal),
    });
  });

  it.each(['http://localhost:8000', 'http://127.0.0.1:8000', 'http://[::1]:8000'])(
    'accepts the loopback API base URL %s',
    (baseUrl) => {
      expect(() =>
        createApiClient({ baseUrl, fetchImplementation: vi.fn<typeof fetch>() }),
      ).not.toThrow();
    },
  );

  it.each([
    'https://api.jobpilot.example.com',
    'http://192.168.1.10:8000',
    'http://0.0.0.0:8000',
    'http://[::]:8000',
  ])('rejects the non-loopback API base URL %s', (baseUrl) => {
    expect(() => createApiClient({ baseUrl, fetchImplementation: vi.fn<typeof fetch>() })).toThrow(
      'API base URL must use a loopback host',
    );
  });

  it('rejects a non-HTTP API base URL', () => {
    expect(() => createApiClient({ baseUrl: 'file:///tmp/jobpilot' })).toThrow(
      'API base URL must use HTTP or HTTPS',
    );
  });

  it('rejects credentials in the API base URL', () => {
    expect(() => createApiClient({ baseUrl: 'http://user:secret@127.0.0.1:8000' })).toThrow(
      'API base URL must not include credentials',
    );
  });

  it.each([201, 204, 503])('rejects the non-200 health response %s', async (status) => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(null, { status }));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.getHealth()).rejects.toThrow(`health request failed with status ${status}`);
  });

  it.each([
    ['wrong status', { status: 'starting', service: 'jobpilot-api' }],
    ['wrong service', { status: 'ok', service: 'remote-api' }],
    ['missing field', { status: 'ok' }],
    ['extra field', { ...healthyPayload, deployment: 'remote' }],
    ['array', [healthyPayload]],
  ])('rejects an untrusted %s health payload', async (_caseName, payload) => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.getHealth()).rejects.toThrow('invalid health response');
  });

  it('rejects invalid health JSON', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response('{', { status: 200 }));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.getHealth()).rejects.toThrow('invalid health response');
  });

  it('aborts a health request that remains pending for five seconds', async () => {
    vi.useFakeTimers();
    const fetchImplementation = vi.fn<typeof fetch>((_input, init) => {
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener(
          'abort',
          () => reject(new DOMException('The operation was aborted', 'AbortError')),
          { once: true },
        );
      });
    });
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    const healthRequest = client.getHealth();
    expect(fetchImplementation.mock.calls[0]?.[1]?.signal).toBeInstanceOf(AbortSignal);
    const timeoutExpectation = expect(healthRequest).rejects.toThrow(
      'JobPilot API health request timed out',
    );
    await vi.advanceTimersByTimeAsync(5_000);
    await timeoutExpectation;
  });
});
