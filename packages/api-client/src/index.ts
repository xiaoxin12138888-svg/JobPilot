import type {
  ApiErrorEnvelope,
  ApiHealthResponse,
  Application,
  ApplicationListResponse,
  ApplicationStatus,
  CreateResumeVersionInput,
  DuplicateResumeVersionInput,
  CreateJobInput,
  Job,
  JobAnalysisResponse,
  JobEvidenceMapResponse,
  JobListResponse,
  JobSource,
  ResumeVersion,
  ResumeVersionListResponse,
  UpdateApplicationInput,
  UpdateJobInput,
  UpdateResumeVersionInput,
} from '@jobpilot/shared-types';
export { APPLICATION_STATUS_LABELS, JOB_SOURCE_LABELS } from '@jobpilot/shared-types';

export type {
  ApiErrorEnvelope,
  ApiHealthResponse,
  Application,
  ApplicationListItem,
  ApplicationListResponse,
  ApplicationStatus,
  CreateJobInput,
  CreateResumeVersionInput,
  DuplicateResumeVersionInput,
  EvidenceCoverage,
  EvidenceItem,
  EvidenceMap,
  EvidenceMapRecord,
  EvidenceMapping,
  EvidenceRequirementType,
  JDAnalysis,
  JDAnalysisRecord,
  Job,
  JobAnalysisResponse,
  JobEvidenceMapResponse,
  JobListItem,
  JobListResponse,
  JobSource,
  ResumeEvidence,
  ResumeVersion,
  ResumeVersionListResponse,
  UpdateApplicationInput,
  UpdateJobInput,
  UpdateResumeVersionInput,
} from '@jobpilot/shared-types';

const REQUEST_TIMEOUT_MILLISECONDS = 5_000;
const ANALYSIS_REQUEST_TIMEOUT_MILLISECONDS = 35_000;
const EVIDENCE_MAP_REQUEST_TIMEOUT_MILLISECONDS = 65_000;
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
  readonly resourceId: string | undefined;

  constructor(status: number, error: ApiErrorEnvelope['error']) {
    super(error.message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.code = error.code;
    this.requestId = error.requestId;
    this.resourceId = error.resourceId;
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
  jobId?: string;
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
  getJobAnalysis(jobId: string): Promise<JobAnalysisResponse>;
  analyzeJob(jobId: string): Promise<JobAnalysisResponse>;
  getJobEvidenceMap(jobId: string, resumeVersionId: string): Promise<JobEvidenceMapResponse>;
  generateJobEvidenceMap(jobId: string, resumeVersionId: string): Promise<JobEvidenceMapResponse>;
  createApplication(jobId: string): Promise<Application>;
  listApplications(filters?: ApplicationListFilters): Promise<ApplicationListResponse>;
  getApplication(applicationId: string): Promise<Application>;
  updateApplication(applicationId: string, input: UpdateApplicationInput): Promise<Application>;
  createResumeVersion(input: CreateResumeVersionInput): Promise<ResumeVersion>;
  listResumeVersions(): Promise<ResumeVersionListResponse>;
  getResumeVersion(resumeVersionId: string): Promise<ResumeVersion>;
  updateResumeVersion(
    resumeVersionId: string,
    input: UpdateResumeVersionInput,
  ): Promise<ResumeVersion>;
  duplicateResumeVersion(
    resumeVersionId: string,
    input: DuplicateResumeVersionInput,
  ): Promise<ResumeVersion>;
  deleteResumeVersion(resumeVersionId: string): Promise<void>;
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
    timeoutMilliseconds = REQUEST_TIMEOUT_MILLISECONDS,
  ): Promise<unknown> {
    const abortController = new AbortController();
    const timeout = setTimeout(() => abortController.abort(), timeoutMilliseconds);
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
    async getJobAnalysis(jobId): Promise<JobAnalysisResponse> {
      return requireJobAnalysis(
        await request(`/api/v1/jobs/${encodeURIComponent(jobId)}/analysis`, 'GET'),
      );
    },
    async analyzeJob(jobId): Promise<JobAnalysisResponse> {
      return requireJobAnalysis(
        await request(
          `/api/v1/jobs/${encodeURIComponent(jobId)}/analysis`,
          'POST',
          {},
          ANALYSIS_REQUEST_TIMEOUT_MILLISECONDS,
        ),
      );
    },
    async getJobEvidenceMap(jobId, resumeVersionId): Promise<JobEvidenceMapResponse> {
      const query = new URLSearchParams({ resumeVersionId });
      return requireJobEvidenceMap(
        await request(
          `/api/v1/jobs/${encodeURIComponent(jobId)}/evidence-map?${query.toString()}`,
          'GET',
        ),
      );
    },
    async generateJobEvidenceMap(jobId, resumeVersionId): Promise<JobEvidenceMapResponse> {
      return requireJobEvidenceMap(
        await request(
          `/api/v1/jobs/${encodeURIComponent(jobId)}/evidence-map`,
          'POST',
          { resumeVersionId, confirmExternalAi: true },
          EVIDENCE_MAP_REQUEST_TIMEOUT_MILLISECONDS,
        ),
      );
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
    async createResumeVersion(input): Promise<ResumeVersion> {
      return requireResumeVersion(await request('/api/v1/resume-versions', 'POST', input));
    },
    async listResumeVersions(): Promise<ResumeVersionListResponse> {
      return requireResumeVersionList(await request('/api/v1/resume-versions', 'GET'));
    },
    async getResumeVersion(resumeVersionId): Promise<ResumeVersion> {
      return requireResumeVersion(
        await request(`/api/v1/resume-versions/${encodeURIComponent(resumeVersionId)}`, 'GET'),
      );
    },
    async updateResumeVersion(resumeVersionId, input): Promise<ResumeVersion> {
      return requireResumeVersion(
        await request(
          `/api/v1/resume-versions/${encodeURIComponent(resumeVersionId)}`,
          'PATCH',
          input,
        ),
      );
    },
    async duplicateResumeVersion(resumeVersionId, input): Promise<ResumeVersion> {
      return requireResumeVersion(
        await request(
          `/api/v1/resume-versions/${encodeURIComponent(resumeVersionId)}/duplicate`,
          'POST',
          input,
        ),
      );
    },
    async deleteResumeVersion(resumeVersionId): Promise<void> {
      await request(`/api/v1/resume-versions/${encodeURIComponent(resumeVersionId)}`, 'DELETE');
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

function requireResumeVersion(value: unknown): ResumeVersion {
  if (!isRecordWithKeys(value, RESUME_VERSION_KEYS) || !isResumeVersionFields(value)) {
    throw new Error('JobPilot API returned an invalid Resume Version response');
  }
  return value as unknown as ResumeVersion;
}

function requireResumeVersionList(value: unknown): ResumeVersionListResponse {
  if (!isPage(value) || !value.items.every(isResumeVersionFieldsWithExactKeys)) {
    throw new Error('JobPilot API returned an invalid Resume Version list response');
  }
  return value as unknown as ResumeVersionListResponse;
}

function requireJobAnalysis(value: unknown): JobAnalysisResponse {
  if (
    !isRecordWithKeys(value, ['isConfigured', 'analysis']) ||
    typeof value.isConfigured !== 'boolean' ||
    (value.analysis !== null && !isJDAnalysisRecord(value.analysis))
  ) {
    throw new Error('JobPilot API returned an invalid Job analysis response');
  }
  return value as unknown as JobAnalysisResponse;
}

function requireJobEvidenceMap(value: unknown): JobEvidenceMapResponse {
  if (
    !isRecordWithKeys(value, ['isConfigured', 'evidenceMap']) ||
    typeof value.isConfigured !== 'boolean' ||
    (value.evidenceMap !== null && !isEvidenceMapRecord(value.evidenceMap))
  ) {
    throw new Error('JobPilot API returned an invalid Evidence Map response');
  }
  return value as unknown as JobEvidenceMapResponse;
}

function isEvidenceMapRecord(value: unknown): boolean {
  return (
    isRecordWithKeys(value, [
      'id',
      'jobId',
      'resumeVersionId',
      'schemaVersion',
      'result',
      'isStale',
      'createdAt',
      'updatedAt',
    ]) &&
    typeof value.id === 'string' &&
    typeof value.jobId === 'string' &&
    typeof value.resumeVersionId === 'string' &&
    value.schemaVersion === 1 &&
    isRecordWithKeys(value.result, ['mappings']) &&
    Array.isArray(value.result.mappings) &&
    value.result.mappings.every(isEvidenceMapping) &&
    typeof value.isStale === 'boolean' &&
    isDateString(value.createdAt) &&
    isDateString(value.updatedAt)
  );
}

function isEvidenceMapping(value: unknown): boolean {
  return (
    isRecordWithKeys(value, [
      'requirementType',
      'requirementText',
      'coverage',
      'resumeEvidence',
      'reason',
    ]) &&
    (value.requirementType === 'MUST_HAVE' || value.requirementType === 'PREFERRED') &&
    typeof value.requirementText === 'string' &&
    (value.coverage === 'DIRECT' || value.coverage === 'PARTIAL' || value.coverage === 'GAP') &&
    Array.isArray(value.resumeEvidence) &&
    value.resumeEvidence.every(
      (item) => isRecordWithKeys(item, ['quote']) && typeof item.quote === 'string',
    ) &&
    typeof value.reason === 'string'
  );
}

function isJDAnalysisRecord(value: unknown): boolean {
  return (
    isRecordWithKeys(value, [
      'id',
      'jobId',
      'schemaVersion',
      'result',
      'isStale',
      'createdAt',
      'updatedAt',
    ]) &&
    typeof value.id === 'string' &&
    typeof value.jobId === 'string' &&
    value.schemaVersion === 1 &&
    isJDAnalysis(value.result) &&
    typeof value.isStale === 'boolean' &&
    isDateString(value.createdAt) &&
    isDateString(value.updatedAt)
  );
}

function isJDAnalysis(value: unknown): boolean {
  return (
    isRecordWithKeys(value, [
      'summary',
      'responsibilities',
      'mustHaveRequirements',
      'preferredRequirements',
      'skills',
      'experienceRequirements',
      'educationRequirements',
      'domainKeywords',
      'interviewFocus',
    ]) &&
    typeof value.summary === 'string' &&
    isEvidenceItems(value.responsibilities) &&
    isEvidenceItems(value.mustHaveRequirements) &&
    isEvidenceItems(value.preferredRequirements) &&
    isStrings(value.skills) &&
    isEvidenceItems(value.experienceRequirements) &&
    isEvidenceItems(value.educationRequirements) &&
    isStrings(value.domainKeywords) &&
    isEvidenceItems(value.interviewFocus)
  );
}

function isEvidenceItems(value: unknown): boolean {
  return (
    Array.isArray(value) &&
    value.every(
      (item) =>
        isRecordWithKeys(item, ['text', 'evidence']) &&
        typeof item.text === 'string' &&
        isNullableString(item.evidence),
    )
  );
}

function isStrings(value: unknown): boolean {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
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
const APPLICATION_KEYS = [
  'id',
  'jobId',
  'status',
  'resumeVersionId',
  'appliedAt',
  'createdAt',
  'updatedAt',
] as const;
const RESUME_VERSION_KEYS = [
  'id',
  'name',
  'content',
  'applicationCount',
  'createdAt',
  'updatedAt',
] as const;

function isJobFields(value: Record<string, unknown>): boolean {
  return (
    typeof value.id === 'string' &&
    typeof value.title === 'string' &&
    typeof value.company === 'string' &&
    isNullableString(value.location) &&
    isNullableString(value.salaryText) &&
    (value.source === 'manual' || value.source === 'boss' || value.source === 'nowcoder') &&
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
    isNullableString(value.resumeVersionId) &&
    (value.appliedAt === null || isDateString(value.appliedAt)) &&
    isDateString(value.createdAt) &&
    isDateString(value.updatedAt)
  );
}

function isResumeVersionFieldsWithExactKeys(value: Record<string, unknown>): boolean {
  return isRecordWithKeys(value, RESUME_VERSION_KEYS) && isResumeVersionFields(value);
}

function isResumeVersionFields(value: Record<string, unknown>): boolean {
  return (
    typeof value.id === 'string' &&
    typeof value.name === 'string' &&
    typeof value.content === 'string' &&
    typeof value.applicationCount === 'number' &&
    Number.isInteger(value.applicationCount) &&
    value.applicationCount >= 0 &&
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
  if (!isRecordWithKeys(value, ['error']) || !isRecord(value.error)) return false;
  const keys = Object.keys(value.error);
  return (
    keys.length >= 3 &&
    keys.length <= 4 &&
    keys.every((key) => ['code', 'message', 'requestId', 'resourceId'].includes(key)) &&
    typeof value.error.code === 'string' &&
    typeof value.error.message === 'string' &&
    typeof value.error.requestId === 'string' &&
    (value.error.resourceId === undefined || typeof value.error.resourceId === 'string')
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
