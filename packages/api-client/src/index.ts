import type { ApiHealthResponse, CsrfTokenResponse, UserView } from '@jobpilot/shared-types';

export type { ApiHealthResponse, UserView } from '@jobpilot/shared-types';

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string) {
    super(`JobPilot API request failed (${status} ${code})`);
    this.name = 'ApiClientError';
    this.status = status;
    this.code = code;
  }
}

export function isAuthenticationRequired(error: unknown): boolean {
  return (
    error instanceof ApiClientError &&
    error.status === 401 &&
    error.code === 'AUTHENTICATION_REQUIRED'
  );
}

export interface ApiClient {
  getHealth(): Promise<ApiHealthResponse>;
  getCurrentUser(): Promise<UserView>;
  getWebCsrfToken(): Promise<string>;
  logoutWebSession(csrfToken?: string): Promise<void>;
  getWebLoginUrl(): string;
}

export interface ExtensionBearerApiClient {
  establishIdentity(accessToken: string): Promise<UserView>;
  getCurrentUser(accessToken: string): Promise<UserView>;
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

function getApiUrl(baseUrl: URL, path: string): string {
  return new URL(path, baseUrl).toString();
}

function isApiHealthResponse(value: unknown): value is ApiHealthResponse {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const response = value as Record<string, unknown>;
  return response.status === 'ok' && response.service === 'jobpilot-api';
}

export function createApiClient(options: ApiClientOptions): ApiClient {
  const baseUrl = validateApiBaseUrl(options.baseUrl);
  const healthUrl = getApiUrl(baseUrl, '/health');
  const currentUserUrl = getApiUrl(baseUrl, '/api/v1/auth/me');
  const csrfUrl = getApiUrl(baseUrl, '/api/v1/auth/csrf');
  const logoutUrl = getApiUrl(baseUrl, '/api/v1/auth/logout');
  const webLoginUrl = new URL('/api/v1/auth/web/authorize', baseUrl);
  webLoginUrl.searchParams.set('intent', 'login');
  webLoginUrl.searchParams.set('returnTo', '/');
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

    async getCurrentUser(): Promise<UserView> {
      const response = await fetchImplementation(currentUserUrl, {
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json' },
      });
      const payload = await readApiJson(response);
      const user = parseUserResponse(payload);
      if (user === undefined) {
        throw invalidApiResponse(response.status);
      }
      return user;
    },

    async getWebCsrfToken(): Promise<string> {
      const response = await fetchImplementation(csrfUrl, {
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json' },
      });
      const payload = await readApiJson(response);
      if (!isCsrfTokenResponse(payload)) {
        throw invalidApiResponse(response.status);
      }
      return payload.data.csrfToken;
    },

    async logoutWebSession(csrfToken?: string): Promise<void> {
      const headers: Record<string, string> = { Accept: 'application/json' };
      if (csrfToken !== undefined) {
        headers['X-CSRF-Token'] = csrfToken;
      }
      const response = await fetchImplementation(logoutUrl, {
        credentials: 'include',
        headers,
        method: 'POST',
      });
      if (!response.ok) {
        throw await apiErrorFromResponse(response);
      }
      if (response.status !== 204) {
        throw invalidApiResponse(response.status);
      }
    },

    getWebLoginUrl(): string {
      return webLoginUrl.toString();
    },
  };
}

export function createExtensionBearerApiClient(
  options: ApiClientOptions,
): ExtensionBearerApiClient {
  const baseUrl = validateExtensionBearerApiBaseUrl(options.baseUrl);
  const establishIdentityUrl = getApiUrl(baseUrl, '/api/v1/auth/session');
  const currentUserUrl = getApiUrl(baseUrl, '/api/v1/auth/me');
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch;

  async function requestUser(
    url: string,
    method: 'GET' | 'POST',
    accessToken: string,
  ): Promise<UserView> {
    if (!isValidAccessCredential(accessToken)) {
      throw new ApiClientError(0, 'INVALID_ACCESS_CREDENTIAL');
    }

    let response: Response;
    try {
      response = await fetchImplementation(url, {
        cache: 'no-store',
        credentials: 'omit',
        headers: {
          Accept: 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        method,
        redirect: 'error',
      });
    } catch {
      throw new ApiClientError(0, 'API_UNAVAILABLE');
    }

    if (response.status !== 200) {
      if (!response.ok) {
        throw await apiErrorFromResponse(response);
      }
      throw invalidApiResponse(response.status);
    }

    const payload = await readApiJson(response);
    const user = parseUserResponse(payload);
    if (user === undefined) {
      throw invalidApiResponse(response.status);
    }
    return user;
  }

  return {
    establishIdentity(accessToken: string): Promise<UserView> {
      return requestUser(establishIdentityUrl, 'POST', accessToken);
    },

    getCurrentUser(accessToken: string): Promise<UserView> {
      return requestUser(currentUserUrl, 'GET', accessToken);
    },
  };
}

export function validateExtensionBearerApiBaseUrl(baseUrl: string): URL {
  const parsedBaseUrl = validateApiBaseUrl(baseUrl);
  const isLoopbackHttp =
    parsedBaseUrl.protocol === 'http:' &&
    (parsedBaseUrl.hostname === 'localhost' ||
      parsedBaseUrl.hostname === '127.0.0.1' ||
      parsedBaseUrl.hostname === '[::1]');

  if (parsedBaseUrl.protocol !== 'https:' && !isLoopbackHttp) {
    throw new Error('Extension bearer API base URL must use HTTPS or loopback HTTP');
  }

  return parsedBaseUrl;
}

function isValidAccessCredential(value: string): boolean {
  return /^[\x21-\x7e]{1,16384}$/u.test(value);
}

async function readApiJson(response: Response): Promise<unknown> {
  if (!response.ok) {
    throw await apiErrorFromResponse(response);
  }
  try {
    return await response.json();
  } catch {
    throw invalidApiResponse(response.status);
  }
}

async function apiErrorFromResponse(response: Response): Promise<ApiClientError> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return new ApiClientError(response.status, 'UNEXPECTED_API_ERROR');
  }

  if (
    isObject(payload) &&
    isObject(payload.error) &&
    isBoundedString(payload.error.code, 100) &&
    API_ERROR_CODE_PATTERN.test(payload.error.code) &&
    isBoundedString(payload.error.message, 500) &&
    typeof payload.error.requestId === 'string' &&
    REQUEST_ID_PATTERN.test(payload.error.requestId)
  ) {
    return new ApiClientError(response.status, payload.error.code);
  }
  return new ApiClientError(response.status, 'UNEXPECTED_API_ERROR');
}

function invalidApiResponse(responseStatus: number): ApiClientError {
  return new ApiClientError(responseStatus, 'INVALID_API_RESPONSE');
}

function parseUserResponse(value: unknown): UserView | undefined {
  if (!isObject(value) || !isObject(value.data)) {
    return undefined;
  }
  const user = value.data;
  if (
    isBoundedString(user.id, 200) &&
    isBoundedString(user.email, 254) &&
    isNullableBoundedString(user.displayName, 100) &&
    isNullableNonEmptyBoundedString(user.locale, 35) &&
    isNullableNonEmptyBoundedString(user.timeZone, 100) &&
    isTimestamp(user.createdAt) &&
    isTimestamp(user.updatedAt)
  ) {
    return {
      id: user.id,
      email: user.email,
      displayName: user.displayName,
      locale: user.locale,
      timeZone: user.timeZone,
      createdAt: user.createdAt,
      updatedAt: user.updatedAt,
    };
  }
  return undefined;
}

function isCsrfTokenResponse(value: unknown): value is CsrfTokenResponse {
  return (
    isObject(value) &&
    isObject(value.data) &&
    isBoundedString(value.data.csrfToken, 512) &&
    !/\s/u.test(value.data.csrfToken)
  );
}

const REQUEST_ID_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/u;
const API_ERROR_CODE_PATTERN = /^[A-Z][A-Z0-9_]{0,99}$/u;
const RFC3339_UTC_TIMESTAMP_PATTERN =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)$/iu;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0;
}

function isBoundedString(value: unknown, maximumLength: number): value is string {
  return isNonEmptyString(value) && value.length <= maximumLength;
}

function isNullableBoundedString(value: unknown, maximumLength: number): value is string | null {
  return value === null || (typeof value === 'string' && value.length <= maximumLength);
}

function isNullableNonEmptyBoundedString(
  value: unknown,
  maximumLength: number,
): value is string | null {
  return value === null || isBoundedString(value, maximumLength);
}

function isTimestamp(value: unknown): value is string {
  if (!isBoundedString(value, 64) || !RFC3339_UTC_TIMESTAMP_PATTERN.test(value)) {
    return false;
  }

  const year = Number(value.slice(0, 4));
  const month = Number(value.slice(5, 7));
  const day = Number(value.slice(8, 10));
  const hour = Number(value.slice(11, 13));
  const minute = Number(value.slice(14, 16));
  const second = Number(value.slice(17, 19));

  return (
    month >= 1 &&
    month <= 12 &&
    day >= 1 &&
    day <= daysInMonth(year, month) &&
    hour <= 23 &&
    minute <= 59 &&
    second <= 59
  );
}

function daysInMonth(year: number, month: number): number {
  if (month === 2) {
    return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28;
  }
  return month === 4 || month === 6 || month === 9 || month === 11 ? 30 : 31;
}
