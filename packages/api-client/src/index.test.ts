import { describe, expect, it, vi } from 'vitest';

import { ApiClientError, createApiClient } from './index';

const healthyPayload = {
  status: 'ok',
  service: 'jobpilot-api',
} as const;

const currentUserPayload = {
  data: {
    id: '019d4a83-cf8c-7f77-a4f0-2cc4131e3138',
    email: 'lin@example.com',
    displayName: 'Lin',
    locale: 'zh-CN',
    timeZone: 'Asia/Shanghai',
    createdAt: '2026-08-30T02:15:00Z',
    updatedAt: '2026-08-30T02:15:00Z',
  },
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

  it('gets and validates the current user through the Web session cookie', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(currentUserPayload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const client = createApiClient({
      baseUrl: 'http://localhost:8000',
      fetchImplementation,
    });

    await expect(client.getCurrentUser()).resolves.toEqual(currentUserPayload.data);
    expect(fetchImplementation).toHaveBeenCalledWith('http://localhost:8000/api/v1/auth/me', {
      cache: 'no-store',
      credentials: 'include',
      headers: { Accept: 'application/json' },
    });
  });

  it('accepts an empty display name allowed by the UserView contract', async () => {
    const payload = {
      data: {
        ...currentUserPayload.data,
        displayName: '',
      },
    };
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const client = createApiClient({
      baseUrl: 'http://localhost:8000',
      fetchImplementation,
    });

    await expect(client.getCurrentUser()).resolves.toEqual(payload.data);
  });

  it('maps a rejected session to a bounded machine-readable client error', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: 'AUTHENTICATION_REQUIRED',
            message: 'Authentication is required',
            requestId: 'req_test',
          },
        }),
        { status: 401, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    const client = createApiClient({
      baseUrl: 'http://localhost:8000',
      fetchImplementation,
    });

    const error = await client.getCurrentUser().catch((caught: unknown) => caught);

    expect(error).toMatchObject({
      name: 'ApiClientError',
      status: 401,
      code: 'AUTHENTICATION_REQUIRED',
    });
    expect(error).not.toHaveProperty(
      'message',
      expect.stringContaining('Authentication is required'),
    );
  });

  it('gets the session-bound CSRF token without caching it', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: { csrfToken: 'csrf-token' } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const client = createApiClient({
      baseUrl: 'http://localhost:8000',
      fetchImplementation,
    });

    await expect(client.getWebCsrfToken()).resolves.toBe('csrf-token');
    expect(fetchImplementation).toHaveBeenCalledWith('http://localhost:8000/api/v1/auth/csrf', {
      cache: 'no-store',
      credentials: 'include',
      headers: { Accept: 'application/json' },
    });
  });

  it('rejects a malformed CSRF response instead of storing it', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: { csrfToken: 'contains whitespace' } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const client = createApiClient({
      baseUrl: 'http://localhost:8000',
      fetchImplementation,
    });

    await expect(client.getWebCsrfToken()).rejects.toEqual(
      new ApiClientError(200, 'INVALID_API_RESPONSE'),
    );
  });

  it('logs out a valid Web session with its CSRF token', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(null, { status: 204 }));
    const client = createApiClient({
      baseUrl: 'http://localhost:8000',
      fetchImplementation,
    });

    await expect(client.logoutWebSession('csrf-token')).resolves.toBeUndefined();
    expect(fetchImplementation).toHaveBeenCalledWith('http://localhost:8000/api/v1/auth/logout', {
      credentials: 'include',
      headers: { Accept: 'application/json', 'X-CSRF-Token': 'csrf-token' },
      method: 'POST',
    });
  });

  it('can clear an already invalid session without inventing a CSRF value', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(null, { status: 204 }));
    const client = createApiClient({
      baseUrl: 'http://localhost:8000',
      fetchImplementation,
    });

    await client.logoutWebSession();

    expect(fetchImplementation).toHaveBeenCalledWith('http://localhost:8000/api/v1/auth/logout', {
      credentials: 'include',
      headers: { Accept: 'application/json' },
      method: 'POST',
    });
  });

  it('builds the fixed top-level Web login URL without exposing OAuth inputs', () => {
    const client = createApiClient({
      baseUrl: 'https://api.jobpilot.example.invalid',
      fetchImplementation: vi.fn<typeof fetch>(),
    });

    expect(client.getWebLoginUrl()).toBe(
      'https://api.jobpilot.example.invalid/api/v1/auth/web/authorize?intent=login&returnTo=%2F',
    );
  });

  it('rejects a non-204 logout response even when it is nominally successful', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify({ data: {} }), { status: 200 }));
    const client = createApiClient({
      baseUrl: 'http://localhost:8000',
      fetchImplementation,
    });

    await expect(client.logoutWebSession('csrf-token')).rejects.toEqual(
      new ApiClientError(200, 'INVALID_API_RESPONSE'),
    );
  });

  it('projects only the approved UserView when v1 adds optional or provider-shaped fields', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {
            ...currentUserPayload.data,
            identitySubject: 'provider-subject-must-not-enter-the-contract',
          },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    const client = createApiClient({
      baseUrl: 'http://localhost:8000',
      fetchImplementation,
    });

    await expect(client.getCurrentUser()).resolves.toEqual(currentUserPayload.data);
  });

  it('rejects an impossible calendar date in a current-user timestamp', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {
            ...currentUserPayload.data,
            createdAt: '2026-02-31T02:15:00Z',
          },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    const client = createApiClient({
      baseUrl: 'http://localhost:8000',
      fetchImplementation,
    });

    await expect(client.getCurrentUser()).rejects.toEqual(
      new ApiClientError(200, 'INVALID_API_RESPONSE'),
    );
  });

  it('rejects a non-UTC current-user timestamp', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {
            ...currentUserPayload.data,
            updatedAt: '2026-08-30T10:15:00+08:00',
          },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    const client = createApiClient({
      baseUrl: 'http://localhost:8000',
      fetchImplementation,
    });

    await expect(client.getCurrentUser()).rejects.toEqual(
      new ApiClientError(200, 'INVALID_API_RESPONSE'),
    );
  });

  it('accepts fractional seconds and an explicit zero offset for RFC 3339 UTC', async () => {
    const utcUser = {
      ...currentUserPayload.data,
      createdAt: '2026-08-30T02:15:00.123456Z',
      updatedAt: '2026-08-30T02:15:00+00:00',
    };
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ data: utcUser }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const client = createApiClient({
      baseUrl: 'http://localhost:8000',
      fetchImplementation,
    });

    await expect(client.getCurrentUser()).resolves.toEqual(utcUser);
  });

  it('does not treat a malformed 401 error envelope as a normal signed-out response', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'AUTHENTICATION_REQUIRED' } }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const client = createApiClient({
      baseUrl: 'http://localhost:8000',
      fetchImplementation,
    });

    await expect(client.getCurrentUser()).rejects.toEqual(
      new ApiClientError(401, 'UNEXPECTED_API_ERROR'),
    );
  });
});
