import { describe, expect, it, vi } from 'vitest';

import {
  ApiClientError,
  createExtensionBearerApiClient,
  type ExtensionBearerApiClient,
} from './index';

const accessToken = 'short-lived-access-token';
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

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function createClient(fetchImplementation: typeof fetch): ExtensionBearerApiClient {
  return createExtensionBearerApiClient({
    baseUrl: 'http://localhost:8000/base-path',
    fetchImplementation,
  });
}

describe('createExtensionBearerApiClient', () => {
  it('establishes the Extension identity with a body-free bearer request', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse(currentUserPayload));
    const client = createClient(fetchImplementation);

    await expect(client.establishIdentity(accessToken)).resolves.toEqual(currentUserPayload.data);
    expect(fetchImplementation).toHaveBeenCalledWith('http://localhost:8000/api/v1/auth/session', {
      cache: 'no-store',
      credentials: 'omit',
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      method: 'POST',
      redirect: 'error',
    });
  });

  it('gets the current user through the same credential-free transport boundary', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse(currentUserPayload));
    const client = createClient(fetchImplementation);

    await expect(client.getCurrentUser(accessToken)).resolves.toEqual(currentUserPayload.data);
    expect(fetchImplementation).toHaveBeenCalledWith('http://localhost:8000/api/v1/auth/me', {
      cache: 'no-store',
      credentials: 'omit',
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      method: 'GET',
      redirect: 'error',
    });
  });

  it('projects only the approved UserView fields from an Extension response', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({
        data: {
          ...currentUserPayload.data,
          identitySubject: 'provider-subject-must-not-cross-the-client-boundary',
          accessToken: 'provider-field-must-not-cross-the-client-boundary',
        },
      }),
    );
    const client = createClient(fetchImplementation);

    await expect(client.establishIdentity(accessToken)).resolves.toEqual(currentUserPayload.data);
  });

  it.each([
    ['empty', ''],
    ['space-containing', 'contains space'],
    ['null-containing', 'contains\0null'],
    ['control-character', 'contains\nnewline'],
    ['delete-character', 'contains\u007fdelete'],
    ['non-ASCII', '令牌'],
    ['oversized', 'x'.repeat(16_385)],
  ])('rejects an %s bearer before any request', async (_caseName, invalidToken) => {
    const fetchImplementation = vi.fn<typeof fetch>();
    const client = createClient(fetchImplementation);

    await expect(client.getCurrentUser(invalidToken)).rejects.toEqual(
      new ApiClientError(0, 'INVALID_ACCESS_CREDENTIAL'),
    );
    expect(fetchImplementation).not.toHaveBeenCalled();
  });

  it.each([
    ['one-character', '!'],
    ['upper-visible-ASCII-boundary', '~'],
    ['maximum-length', 'x'.repeat(16_384)],
  ])('accepts a %s bearer boundary', async (_caseName, validToken) => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse(currentUserPayload));
    const client = createClient(fetchImplementation);

    await expect(client.getCurrentUser(validToken)).resolves.toEqual(currentUserPayload.data);
    expect(fetchImplementation).toHaveBeenCalledOnce();
  });

  it('preserves a malformed 401 status while discarding the untrusted API envelope', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: 'AUTHENTICATION_REQUIRED',
            message: `untrusted ${accessToken}`,
          },
        },
        401,
      ),
    );
    const client = createClient(fetchImplementation);

    const error = await client.getCurrentUser(accessToken).catch((caught: unknown) => caught);

    expect(error).toEqual(new ApiClientError(401, 'UNEXPECTED_API_ERROR'));
    expect(JSON.stringify(error)).not.toContain(accessToken);
  });

  it('discards a credential-shaped error code from an otherwise valid 401 envelope', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: accessToken,
            message: 'Authentication is required',
            requestId: 'req_test',
          },
        },
        401,
      ),
    );
    const client = createClient(fetchImplementation);

    const error = await client.getCurrentUser(accessToken).catch((caught: unknown) => caught);

    expect(error).toEqual(new ApiClientError(401, 'UNEXPECTED_API_ERROR'));
    expect(JSON.stringify(error)).not.toContain(accessToken);
  });

  it('sanitizes a transport failure without retaining its cause or bearer', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockRejectedValue(new Error(`network diagnostic ${accessToken}`));
    const client = createClient(fetchImplementation);

    const error = await client.getCurrentUser(accessToken).catch((caught: unknown) => caught);

    expect(error).toEqual(new ApiClientError(0, 'API_UNAVAILABLE'));
    expect(error).not.toHaveProperty('cause');
    expect(JSON.stringify(error)).not.toContain(accessToken);
  });

  it.each([
    [jsonResponse({ data: {} }), new ApiClientError(200, 'INVALID_API_RESPONSE')],
    [jsonResponse(currentUserPayload, 201), new ApiClientError(201, 'INVALID_API_RESPONSE')],
  ])('rejects a malformed success contract', async (response, expectedError) => {
    const client = createClient(vi.fn<typeof fetch>().mockResolvedValue(response));

    await expect(client.getCurrentUser(accessToken)).rejects.toEqual(expectedError);
  });

  it.each([
    'http://example.com',
    'http://localhost.example.com',
    'http://127.0.0.2:8000',
    'http://192.168.1.20:8000',
  ])('rejects a non-loopback cleartext bearer origin: %s', (baseUrl) => {
    expect(() =>
      createExtensionBearerApiClient({ baseUrl, fetchImplementation: vi.fn<typeof fetch>() }),
    ).toThrow('Extension bearer API base URL must use HTTPS or loopback HTTP');
  });

  it.each([
    'https://api.jobpilot.example.invalid',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://[::1]:8000',
  ])('accepts a secure or loopback bearer origin: %s', (baseUrl) => {
    expect(() =>
      createExtensionBearerApiClient({ baseUrl, fetchImplementation: vi.fn<typeof fetch>() }),
    ).not.toThrow();
  });

  it('rejects a non-HTTP protocol even when its hostname is loopback', () => {
    expect(() =>
      createExtensionBearerApiClient({
        baseUrl: 'ftp://localhost',
        fetchImplementation: vi.fn<typeof fetch>(),
      }),
    ).toThrow('API base URL must use HTTP or HTTPS');
  });
});
