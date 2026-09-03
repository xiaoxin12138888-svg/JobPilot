import type {
  ApiErrorEnvelope,
  ApiHealthResponse,
  Application,
  ApplicationListResponse,
  ApplicationStatus,
  CreateJobInput,
  Job,
  JobListResponse,
  JobSource,
  UpdateApplicationInput,
  UpdateJobInput,
} from '@jobpilot/shared-types';
export { APPLICATION_STATUS_LABELS } from '@jobpilot/shared-types';

export type {
  ApiErrorEnvelope,
  ApiHealthResponse,
  Application,
  ApplicationListItem,
  ApplicationListResponse,
  ApplicationStatus,
  CreateJobInput,
  Job,
  JobListItem,
  JobListResponse,
  JobSource,
  UpdateApplicationInput,
  UpdateJobInput,
} from '@jobpilot/shared-types';

const REQUEST_TIMEOUT_MILLISECONDS = 5_000;
const APPLICATION_STATUSES = new Set<ApplicationStatus>([
  'planned',
  'applied',
  'screening',
  'assessment',
  'interviewing',
  'offer',
  'rejected',
  'withdrawn',
  'closed',
]);

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string;

  constructor(status: number, error: ApiErrorEnvelope['error']) {
    super(error.message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.code = error.code;
    this.requestId = error.requestId;
  }
}

export interface JobListFilters {
  keyword?: string;
  source?: JobSource;
  applicationStatus?: ApplicationStatus;
  limit?: number;
  offset?: number;
}

export interface ApplicationListFilters {
  status?: ApplicationStatus;
  limit?: number;
  offset?: number;
}

export interface ApiClient {
  getHealth(): Promise<ApiHealthResponse>;
  createJob(input: CreateJobInput): Promise<Job>;
  listJobs(filters?: JobListFilters): Promise<JobListResponse>;
  getJob(jobId: string): Promise<Job>;
  updateJob(jobId: string, input: UpdateJobInput): Promise<Job>;
  deleteJob(jobId: string): Promise<void>;
  createApplication(jobId: string): Promise<Application>;
  listApplications(filters?: ApplicationListFilters): Promise<ApplicationListResponse>;
  getApplication(applicationId: string): Promise<Application>;
  updateApplication(applicationId: string, input: UpdateApplicationInput): Promise<Application>;
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
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch;

  async function request(
    path: string,
    method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
    body?: unknown,
  ): Promise<unknown> {
    const abortController = new AbortController();
    const timeout = setTimeout(() => abortController.abort(), REQUEST_TIMEOUT_MILLISECONDS);
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
    }
    try {
      const response = await fetchImplementation(new URL(path, baseUrl).toString(), {
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        cache: 'no-store',
        credentials: 'omit',
        headers,
        method,
        redirect: 'error',
        signal: abortController.signal,
      });
      if (response.status === 204) {
        if (method === 'DELETE') return undefined;
        throw new Error('JobPilot API returned an unexpected empty response');
      }
      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        throw new Error('JobPilot API returned invalid JSON');
      }
      if (!response.ok) {
        if (isApiErrorEnvelope(payload)) {
          throw new ApiRequestError(response.status, payload.error);
        }
        throw new Error(`JobPilot API request failed with status ${response.status}`);
      }
      return payload;
    } catch (error) {
      if (abortController.signal.aborted) {
        throw new Error('JobPilot API request timed out', { cause: error });
      }
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }

  return {
    async getHealth(): Promise<ApiHealthResponse> {
      const abortController = new AbortController();
      const timeout = setTimeout(() => abortController.abort(), REQUEST_TIMEOUT_MILLISECONDS);
      try {
        const response = await fetchImplementation(new URL('/health', baseUrl).toString(), {
          cache: 'no-store',
          credentials: 'omit',
          headers: { Accept: 'application/json' },
          method: 'GET',
          redirect: 'error',
          signal: abortController.signal,
        });
        if (response.status !== 200) {
          throw new Error(`JobPilot API health request failed with status ${response.status}`);
        }
        let payload: unknown;
        try {
          payload = await response.json();
        } catch {
          if (abortController.signal.aborted) {
            throw new Error('JobPilot API health request timed out');
          }
          throw new Error('JobPilot API returned an invalid health response');
        }
        if (!isApiHealthResponse(payload)) {
          throw new Error('JobPilot API returned an invalid health response');
        }
        return payload;
      } catch (error) {
        if (abortController.signal.aborted) {
          throw new Error('JobPilot API health request timed out', { cause: error });
        }
        throw error;
      } finally {
        clearTimeout(timeout);
      }
    },
    async createJob(input): Promise<Job> {
      return requireJob(await request('/api/v1/jobs', 'POST', input));
    },
    async listJobs(filters = {}): Promise<JobListResponse> {
      const query = buildQuery(filters);
      return requireJobList(await request(`/api/v1/jobs${query}`, 'GET'));
    },
    async getJob(jobId): Promise<Job> {
      return requireJob(await request(`/api/v1/jobs/${encodeURIComponent(jobId)}`, 'GET'));
    },
    async updateJob(jobId, input): Promise<Job> {
      return requireJob(await request(`/api/v1/jobs/${encodeURIComponent(jobId)}`, 'PATCH', input));
    },
    async deleteJob(jobId): Promise<void> {
      await request(`/api/v1/jobs/${encodeURIComponent(jobId)}`, 'DELETE');
    },
    async createApplication(jobId): Promise<Application> {
      return requireApplication(
        await request(`/api/v1/jobs/${encodeURIComponent(jobId)}/application`, 'POST', {}),
      );
    },
    async listApplications(filters = {}): Promise<ApplicationListResponse> {
      const query = buildQuery(filters);
      return requireApplicationList(await request(`/api/v1/applications${query}`, 'GET'));
    },
    async getApplication(applicationId): Promise<Application> {
      return requireApplication(
        await request(`/api/v1/applications/${encodeURIComponent(applicationId)}`, 'GET'),
      );
    },
    async updateApplication(applicationId, input): Promise<Application> {
      return requireApplication(
        await request(`/api/v1/applications/${encodeURIComponent(applicationId)}`, 'PATCH', input),
      );
    },
  };
}

function buildQuery(filters: object): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') query.set(key, String(value));
  }
  const text = query.toString();
  return text ? `?${text}` : '';
}

function requireJob(value: unknown): Job {
  if (!isRecordWithKeys(value, JOB_KEYS) || !isJobFields(value)) {
    throw new Error('JobPilot API returned an invalid Job response');
  }
  return value as unknown as Job;
}

function requireJobList(value: unknown): JobListResponse {
  if (
    !isPage(value) ||
    !value.items.every(
      (item) =>
        isRecordWithKeys(item, [...JOB_KEYS, 'applicationStatus']) &&
        isJobFields(item) &&
        (item.applicationStatus === null || isApplicationStatus(item.applicationStatus)),
    )
  ) {
    throw new Error('JobPilot API returned an invalid Job list response');
  }
  return value as unknown as JobListResponse;
}

function requireApplication(value: unknown): Application {
  if (!isRecordWithKeys(value, APPLICATION_KEYS) || !isApplicationFields(value)) {
    throw new Error('JobPilot API returned an invalid Application response');
  }
  return value as unknown as Application;
}

function requireApplicationList(value: unknown): ApplicationListResponse {
  if (
    !isPage(value) ||
    !value.items.every(
      (item) =>
        isRecordWithKeys(item, [...APPLICATION_KEYS, 'jobTitle', 'company']) &&
        isApplicationFields(item) &&
        typeof item.jobTitle === 'string' &&
        typeof item.company === 'string',
    )
  ) {
    throw new Error('JobPilot API returned an invalid Application list response');
  }
  return value as unknown as ApplicationListResponse;
}

const JOB_KEYS = [
  'id',
  'title',
  'company',
  'location',
  'salaryText',
  'source',
  'sourceUrl',
  'description',
  'notes',
  'createdAt',
  'updatedAt',
] as const;
const APPLICATION_KEYS = ['id', 'jobId', 'status', 'appliedAt', 'createdAt', 'updatedAt'] as const;

function isJobFields(value: Record<string, unknown>): boolean {
  return (
    typeof value.id === 'string' &&
    typeof value.title === 'string' &&
    typeof value.company === 'string' &&
    isNullableString(value.location) &&
    isNullableString(value.salaryText) &&
    value.source === 'manual' &&
    isNullableString(value.sourceUrl) &&
    isNullableString(value.description) &&
    isNullableString(value.notes) &&
    isDateString(value.createdAt) &&
    isDateString(value.updatedAt)
  );
}

function isApplicationFields(value: Record<string, unknown>): boolean {
  return (
    typeof value.id === 'string' &&
    typeof value.jobId === 'string' &&
    isApplicationStatus(value.status) &&
    (value.appliedAt === null || isDateString(value.appliedAt)) &&
    isDateString(value.createdAt) &&
    isDateString(value.updatedAt)
  );
}

function isPage(value: unknown): value is {
  items: Record<string, unknown>[];
  total: number;
  limit: number;
  offset: number;
} {
  return (
    isRecordWithKeys(value, ['items', 'total', 'limit', 'offset']) &&
    Array.isArray(value.items) &&
    value.items.every(isRecord) &&
    typeof value.total === 'number' &&
    Number.isInteger(value.total) &&
    value.total >= 0 &&
    typeof value.limit === 'number' &&
    Number.isInteger(value.limit) &&
    value.limit >= 1 &&
    value.limit <= 100 &&
    typeof value.offset === 'number' &&
    Number.isInteger(value.offset) &&
    value.offset >= 0
  );
}

function isApiHealthResponse(value: unknown): value is ApiHealthResponse {
  return (
    isRecordWithKeys(value, ['status', 'service']) &&
    value.status === 'ok' &&
    value.service === 'jobpilot-api'
  );
}

function isApiErrorEnvelope(value: unknown): value is ApiErrorEnvelope {
  return (
    isRecordWithKeys(value, ['error']) &&
    isRecordWithKeys(value.error, ['code', 'message', 'requestId']) &&
    typeof value.error.code === 'string' &&
    typeof value.error.message === 'string' &&
    typeof value.error.requestId === 'string'
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isRecordWithKeys(
  value: unknown,
  keys: readonly string[],
): value is Record<string, unknown> {
  return (
    isRecord(value) &&
    Object.keys(value).length === keys.length &&
    keys.every((key) => key in value)
  );
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string';
}

function isDateString(value: unknown): value is string {
  return typeof value === 'string' && !Number.isNaN(Date.parse(value));
}

function isApplicationStatus(value: unknown): value is ApplicationStatus {
  return typeof value === 'string' && APPLICATION_STATUSES.has(value as ApplicationStatus);
}

function isLoopbackHostname(hostname: string): boolean {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]';
}
