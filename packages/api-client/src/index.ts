import type { ApiHealthResponse } from '@jobpilot/shared-types';

export type { ApiHealthResponse } from '@jobpilot/shared-types';

export interface ApiClient {
  getHealth(): Promise<ApiHealthResponse>;
}

export interface ApiClientOptions {
  baseUrl: string;
  fetchImplementation?: typeof fetch;
}

export function validateApiBaseUrl(baseUrl: string): URL {
  let parsedBaseUrl: URL;

  try {
    parsedBaseUrl = new URL(baseUrl);
  } catch {
    throw new Error('API base URL must be a valid absolute URL');
  }

  if (parsedBaseUrl.protocol !== 'http:' && parsedBaseUrl.protocol !== 'https:') {
    throw new Error('API base URL must use HTTP or HTTPS');
  }
  if (parsedBaseUrl.username || parsedBaseUrl.password) {
    throw new Error('API base URL must not include credentials');
  }
  if (!isLoopbackHostname(parsedBaseUrl.hostname)) {
    throw new Error('API base URL must use a loopback host');
  }

  return parsedBaseUrl;
}

export function createApiClient(options: ApiClientOptions): ApiClient {
  const baseUrl = validateApiBaseUrl(options.baseUrl);
  const healthUrl = new URL('/health', baseUrl).toString();
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch;

  return {
    async getHealth(): Promise<ApiHealthResponse> {
      const response = await fetchImplementation(healthUrl, {
        cache: 'no-store',
        credentials: 'omit',
        headers: { Accept: 'application/json' },
        method: 'GET',
        redirect: 'error',
      });

      if (response.status !== 200) {
        throw new Error(`JobPilot API health request failed with status ${response.status}`);
      }

      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        throw new Error('JobPilot API returned an invalid health response');
      }
      if (!isApiHealthResponse(payload)) {
        throw new Error('JobPilot API returned an invalid health response');
      }
      return payload;
    },
  };
}

function isApiHealthResponse(value: unknown): value is ApiHealthResponse {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return false;
  }
  const response = value as Record<string, unknown>;
  return (
    Object.keys(response).length === 2 &&
    response.status === 'ok' &&
    response.service === 'jobpilot-api'
  );
}

function isLoopbackHostname(hostname: string): boolean {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]';
}
