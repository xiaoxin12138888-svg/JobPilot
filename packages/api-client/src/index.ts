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

  return parsedBaseUrl;
}

function getHealthUrl(baseUrl: string): string {
  return new URL('/health', validateApiBaseUrl(baseUrl)).toString();
}

function isApiHealthResponse(value: unknown): value is ApiHealthResponse {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const response = value as Record<string, unknown>;
  return response.status === 'ok' && response.service === 'jobpilot-api';
}

export function createApiClient(options: ApiClientOptions): ApiClient {
  const healthUrl = getHealthUrl(options.baseUrl);
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch;

  return {
    async getHealth(): Promise<ApiHealthResponse> {
      const response = await fetchImplementation(healthUrl, {
        headers: { Accept: 'application/json' },
      });

      if (!response.ok) {
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
