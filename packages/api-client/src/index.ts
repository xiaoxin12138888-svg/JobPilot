import type {
  ApiErrorEnvelope,
  ApiHealthResponse,
  Application,
  ApplicationListResponse,
  ApplicationStatus,
  AutofillProfileInput,
  AutofillProfileResponse,
  ConfirmResumeImportInput,
  CopilotResponse,
  CreateInterviewQuestionInput,
  CreateInterviewRoundInput,
  CreateResumeVersionInput,
  DuplicateResumeVersionInput,
  FeedbackSummary,
  InterviewQuestion,
  InterviewRound,
  InterviewRoundListResponse,
  CreateJobInput,
  Job,
  JobAnalysisResponse,
  JobEvidenceMapResponse,
  JobListResponse,
  JobSource,
  ResumeVersion,
  ResumeVersionListResponse,
  ResumeImportConfirmResponse,
  ResumeImportParseResponse,
  UpdateInterviewQuestionInput,
  UpdateInterviewRoundInput,
  UpdateApplicationInput,
  UpdateJobInput,
  UpdateResumeVersionInput,
} from '@jobpilot/shared-types';

import { requireCopilotResponse } from './copilot-validation.ts';
import { isDateString, isNullableString, isRecord, isRecordWithKeys } from './validation.ts';

export {
  APPLICATION_STATUS_LABELS,
  INTERVIEW_STATUS_LABELS,
  INTERVIEW_TYPE_LABELS,
  JOB_SOURCE_LABELS,
  QUESTION_CATEGORY_LABELS,
  QUESTION_PERFORMANCE_LABELS,
  REJECTION_REASON_LABELS,
} from '@jobpilot/shared-types';

export type {
  ApiErrorEnvelope,
  ApiHealthResponse,
  Application,
  ApplicationListItem,
  ApplicationListResponse,
  ApplicationStatus,
  AutofillEducationEntry,
  AutofillExperienceEntry,
  AutofillProjectEntry,
  AutofillPersonalDetails,
  AutofillProfile,
  AutofillProfileInput,
  AutofillProfileLinks,
  AutofillProfileResponse,
  CopilotInterviewCategory,
  CopilotInterviewQuestion,
  CopilotInterviewReview,
  CopilotKind,
  CopilotRecord,
  CopilotResponse,
  CopilotSourceEvidence,
  CopilotSourceType,
  CreateJobInput,
  CreateInterviewQuestionInput,
  CreateInterviewRoundInput,
  CreateResumeVersionInput,
  DuplicateResumeVersionInput,
  EvidenceCoverage,
  EvidenceItem,
  EvidenceMap,
  EvidenceMapRecord,
  EvidenceMapSchemaVersion,
  EvidenceMapping,
  EvidenceRequirementType,
  FeedbackGroupStats,
  FeedbackSummary,
  FeedbackTotals,
  FunnelStage,
  FunnelStageName,
  GroundedCopilotItem,
  InterviewQuestion,
  InterviewRound,
  InterviewRoundListResponse,
  InterviewStatus,
  InterviewType,
  InterviewPrepResult,
  JDAnalysis,
  JDAnalysisRecord,
  Job,
  JobAnalysisResponse,
  JobMatchResult,
  JobEvidenceMapResponse,
  JobListItem,
  JobListResponse,
  JobSource,
  ResumeEvidence,
  ResumeAdviceResult,
  ResumeVersion,
  ResumeVersionListResponse,
  ResumeImportBlock,
  ResumeImportBlockKind,
  ResumeImportConfirmResponse,
  ResumeImportEducationCandidate,
  ResumeImportExperienceCandidate,
  ResumeImportProjectCandidate,
  ResumeImportFileType,
  ResumeImportParseResponse,
  ResumeImportSection,
  ResumeImportSectionKind,
  ResumeProfileImportInput,
  ConfirmResumeImportInput,
  ResumeVersionFeedbackStats,
  RejectionReason,
  SourceFeedbackStats,
  UpdateApplicationInput,
  UpdateJobInput,
  UpdateInterviewQuestionInput,
  UpdateInterviewRoundInput,
  UpdateResumeVersionInput,
  QuestionCategory,
  QuestionPerformance,
} from '@jobpilot/shared-types';

const REQUEST_TIMEOUT_MILLISECONDS = 5_000;
const ANALYSIS_REQUEST_TIMEOUT_MILLISECONDS = 35_000;
const EVIDENCE_MAP_REQUEST_TIMEOUT_MILLISECONDS = 65_000;
const COPILOT_REQUEST_TIMEOUT_MILLISECONDS = 65_000;
const RESUME_PARSE_REQUEST_TIMEOUT_MILLISECONDS = 15_000;
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

export interface InterviewListFilters {
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
  getJobMatch(jobId: string, resumeVersionId: string): Promise<CopilotResponse>;
  generateJobMatch(jobId: string, resumeVersionId: string): Promise<CopilotResponse>;
  getResumeAdvice(jobId: string, resumeVersionId: string): Promise<CopilotResponse>;
  generateResumeAdvice(jobId: string, resumeVersionId: string): Promise<CopilotResponse>;
  getInterviewPrep(jobId: string): Promise<CopilotResponse>;
  generateInterviewPrep(jobId: string): Promise<CopilotResponse>;
  getCopilotRecord(recordId: string): Promise<CopilotResponse>;
  createApplication(jobId: string): Promise<Application>;
  listApplications(filters?: ApplicationListFilters): Promise<ApplicationListResponse>;
  getApplication(applicationId: string): Promise<Application>;
  updateApplication(applicationId: string, input: UpdateApplicationInput): Promise<Application>;
  createInterview(applicationId: string, input: CreateInterviewRoundInput): Promise<InterviewRound>;
  listInterviews(
    applicationId: string,
    filters?: InterviewListFilters,
  ): Promise<InterviewRoundListResponse>;
  getInterview(interviewId: string): Promise<InterviewRound>;
  updateInterview(interviewId: string, input: UpdateInterviewRoundInput): Promise<InterviewRound>;
  deleteInterview(interviewId: string): Promise<void>;
  createInterviewQuestion(
    interviewId: string,
    input: CreateInterviewQuestionInput,
  ): Promise<InterviewQuestion>;
  updateInterviewQuestion(
    questionId: string,
    input: UpdateInterviewQuestionInput,
  ): Promise<InterviewQuestion>;
  deleteInterviewQuestion(questionId: string): Promise<void>;
  getFeedbackSummary(): Promise<FeedbackSummary>;
  getAutofillProfile(): Promise<AutofillProfileResponse>;
  replaceAutofillProfile(input: AutofillProfileInput): Promise<AutofillProfileResponse>;
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
  parseResumeImport(file: File): Promise<ResumeImportParseResponse>;
  confirmResumeImport(input: ConfirmResumeImportInput): Promise<ResumeImportConfirmResponse>;
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
    method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
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

  async function requestMultipart(path: string, formData: FormData): Promise<unknown> {
    const abortController = new AbortController();
    const timeout = setTimeout(
      () => abortController.abort(),
      RESUME_PARSE_REQUEST_TIMEOUT_MILLISECONDS,
    );
    try {
      const response = await fetchImplementation(new URL(path, baseUrl).toString(), {
        body: formData,
        cache: 'no-store',
        credentials: 'omit',
        headers: { Accept: 'application/json' },
        method: 'POST',
        redirect: 'error',
        signal: abortController.signal,
      });
      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        throw new Error('JobPilot API returned invalid JSON');
      }
      if (!response.ok) {
        if (isApiErrorEnvelope(payload)) throw new ApiRequestError(response.status, payload.error);
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
    async getJobMatch(jobId, resumeVersionId): Promise<CopilotResponse> {
      const query = new URLSearchParams({ resumeVersionId });
      return requireCopilotResponse(
        await request(
          `/api/v1/jobs/${encodeURIComponent(jobId)}/copilot/match?${query.toString()}`,
          'GET',
        ),
      );
    },
    async generateJobMatch(jobId, resumeVersionId): Promise<CopilotResponse> {
      return requireCopilotResponse(
        await request(
          `/api/v1/jobs/${encodeURIComponent(jobId)}/copilot/match`,
          'POST',
          { resumeVersionId, confirmExternalAi: true },
          COPILOT_REQUEST_TIMEOUT_MILLISECONDS,
        ),
      );
    },
    async getResumeAdvice(jobId, resumeVersionId): Promise<CopilotResponse> {
      const query = new URLSearchParams({ resumeVersionId });
      return requireCopilotResponse(
        await request(
          `/api/v1/jobs/${encodeURIComponent(jobId)}/copilot/resume-advice?${query.toString()}`,
          'GET',
        ),
      );
    },
    async generateResumeAdvice(jobId, resumeVersionId): Promise<CopilotResponse> {
      return requireCopilotResponse(
        await request(
          `/api/v1/jobs/${encodeURIComponent(jobId)}/copilot/resume-advice`,
          'POST',
          { resumeVersionId, confirmExternalAi: true },
          COPILOT_REQUEST_TIMEOUT_MILLISECONDS,
        ),
      );
    },
    async getInterviewPrep(jobId): Promise<CopilotResponse> {
      return requireCopilotResponse(
        await request(`/api/v1/jobs/${encodeURIComponent(jobId)}/copilot/interview-prep`, 'GET'),
      );
    },
    async generateInterviewPrep(jobId): Promise<CopilotResponse> {
      return requireCopilotResponse(
        await request(
          `/api/v1/jobs/${encodeURIComponent(jobId)}/copilot/interview-prep`,
          'POST',
          { confirmExternalAi: true },
          COPILOT_REQUEST_TIMEOUT_MILLISECONDS,
        ),
      );
    },
    async getCopilotRecord(recordId): Promise<CopilotResponse> {
      return requireCopilotResponse(
        await request(`/api/v1/copilot/${encodeURIComponent(recordId)}`, 'GET'),
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
    async createInterview(applicationId, input): Promise<InterviewRound> {
      return requireInterviewRound(
        await request(
          `/api/v1/applications/${encodeURIComponent(applicationId)}/interviews`,
          'POST',
          input,
        ),
      );
    },
    async listInterviews(applicationId, filters = {}): Promise<InterviewRoundListResponse> {
      const query = buildQuery(filters);
      return requireInterviewRoundList(
        await request(
          `/api/v1/applications/${encodeURIComponent(applicationId)}/interviews${query}`,
          'GET',
        ),
      );
    },
    async getInterview(interviewId): Promise<InterviewRound> {
      return requireInterviewRound(
        await request(`/api/v1/interviews/${encodeURIComponent(interviewId)}`, 'GET'),
      );
    },
    async updateInterview(interviewId, input): Promise<InterviewRound> {
      return requireInterviewRound(
        await request(`/api/v1/interviews/${encodeURIComponent(interviewId)}`, 'PATCH', input),
      );
    },
    async deleteInterview(interviewId): Promise<void> {
      await request(`/api/v1/interviews/${encodeURIComponent(interviewId)}`, 'DELETE');
    },
    async createInterviewQuestion(interviewId, input): Promise<InterviewQuestion> {
      return requireInterviewQuestion(
        await request(
          `/api/v1/interviews/${encodeURIComponent(interviewId)}/questions`,
          'POST',
          input,
        ),
      );
    },
    async updateInterviewQuestion(questionId, input): Promise<InterviewQuestion> {
      return requireInterviewQuestion(
        await request(
          `/api/v1/interview-questions/${encodeURIComponent(questionId)}`,
          'PATCH',
          input,
        ),
      );
    },
    async deleteInterviewQuestion(questionId): Promise<void> {
      await request(`/api/v1/interview-questions/${encodeURIComponent(questionId)}`, 'DELETE');
    },
    async getFeedbackSummary(): Promise<FeedbackSummary> {
      return requireFeedbackSummary(await request('/api/v1/feedback-summary', 'GET'));
    },
    async getAutofillProfile(): Promise<AutofillProfileResponse> {
      return requireAutofillProfileResponse(await request('/api/v1/autofill-profile', 'GET'));
    },
    async replaceAutofillProfile(input): Promise<AutofillProfileResponse> {
      return requireAutofillProfileResponse(
        await request('/api/v1/autofill-profile', 'PUT', input),
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
    async parseResumeImport(file): Promise<ResumeImportParseResponse> {
      const formData = new FormData();
      formData.append('file', file, file.name);
      return requireResumeImportParse(
        await requestMultipart('/api/v1/resume-imports/parse', formData),
      );
    },
    async confirmResumeImport(input): Promise<ResumeImportConfirmResponse> {
      return requireResumeImportConfirm(
        await request('/api/v1/resume-imports/confirm', 'POST', input),
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

function requireInterviewRound(value: unknown): InterviewRound {
  if (!isInterviewRound(value)) {
    throw new Error('JobPilot API returned an invalid Interview response');
  }
  return value as InterviewRound;
}

function requireInterviewRoundList(value: unknown): InterviewRoundListResponse {
  if (!isPage(value) || !value.items.every(isInterviewRound)) {
    throw new Error('JobPilot API returned an invalid Interview list response');
  }
  return value as unknown as InterviewRoundListResponse;
}

function requireInterviewQuestion(value: unknown): InterviewQuestion {
  if (!isInterviewQuestion(value)) {
    throw new Error('JobPilot API returned an invalid Interview Question response');
  }
  return value as InterviewQuestion;
}

function requireFeedbackSummary(value: unknown): FeedbackSummary {
  if (!isFeedbackSummary(value)) {
    throw new Error('JobPilot API returned an invalid Feedback Summary response');
  }
  return value as FeedbackSummary;
}

function requireAutofillProfileResponse(value: unknown): AutofillProfileResponse {
  if (
    !isRecordWithKeys(value, ['profile']) ||
    (value.profile !== null && !isAutofillProfile(value.profile))
  ) {
    throw new Error('JobPilot API returned an invalid Autofill Profile response');
  }
  return value as unknown as AutofillProfileResponse;
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

function requireResumeImportParse(value: unknown): ResumeImportParseResponse {
  if (!isResumeImportParse(value)) {
    throw new Error('JobPilot API returned an invalid Resume Import preview');
  }
  return value as ResumeImportParseResponse;
}

function requireResumeImportConfirm(value: unknown): ResumeImportConfirmResponse {
  if (
    !isRecordWithKeys(value, ['resumeVersion', 'profile']) ||
    (value.resumeVersion !== null &&
      (!isRecord(value.resumeVersion) ||
        !isResumeVersionFieldsWithExactKeys(value.resumeVersion))) ||
    (value.profile !== null && !isAutofillProfile(value.profile))
  ) {
    throw new Error('JobPilot API returned an invalid Resume Import confirmation');
  }
  return value as unknown as ResumeImportConfirmResponse;
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
  if (
    !isRecordWithKeys(value, [
      'id',
      'jobId',
      'resumeVersionId',
      'schemaVersion',
      'result',
      'isStale',
      'createdAt',
      'updatedAt',
    ]) ||
    (value.schemaVersion !== 1 && value.schemaVersion !== 2)
  ) {
    return false;
  }
  return (
    typeof value.id === 'string' &&
    typeof value.jobId === 'string' &&
    typeof value.resumeVersionId === 'string' &&
    isRecordWithKeys(value.result, ['mappings']) &&
    Array.isArray(value.result.mappings) &&
    value.result.mappings.every((mapping) =>
      isEvidenceMapping(mapping, value.schemaVersion as 1 | 2),
    ) &&
    typeof value.isStale === 'boolean' &&
    isDateString(value.createdAt) &&
    isDateString(value.updatedAt)
  );
}

function isEvidenceMapping(value: unknown, schemaVersion: 1 | 2): boolean {
  return (
    isRecordWithKeys(value, [
      'requirementType',
      'requirementText',
      'coverage',
      'resumeEvidence',
      'reason',
    ]) &&
    isEvidenceRequirementType(value.requirementType, schemaVersion) &&
    typeof value.requirementText === 'string' &&
    (value.coverage === 'DIRECT' || value.coverage === 'PARTIAL' || value.coverage === 'GAP') &&
    Array.isArray(value.resumeEvidence) &&
    value.resumeEvidence.every(
      (item) => isRecordWithKeys(item, ['quote']) && typeof item.quote === 'string',
    ) &&
    typeof value.reason === 'string'
  );
}

function isEvidenceRequirementType(value: unknown, schemaVersion: 1 | 2): boolean {
  if (value === 'MUST_HAVE' || value === 'PREFERRED') return true;
  return (
    schemaVersion === 2 &&
    (value === 'RESPONSIBILITY' ||
      value === 'SKILL' ||
      value === 'EXPERIENCE' ||
      value === 'EDUCATION')
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
  'outcomeNote',
  'rejectionReason',
  'appliedAt',
  'createdAt',
  'updatedAt',
] as const;
const INTERVIEW_QUESTION_KEYS = [
  'id',
  'interviewRoundId',
  'question',
  'category',
  'answerSummary',
  'performance',
  'note',
  'createdAt',
  'updatedAt',
] as const;
const INTERVIEW_ROUND_KEYS = [
  'id',
  'applicationId',
  'roundName',
  'interviewType',
  'scheduledAt',
  'status',
  'interviewerNote',
  'wentWell',
  'couldImprove',
  'learningNotes',
  'otherNotes',
  'questions',
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
const AUTOFILL_EDUCATION_KEYS = ['school', 'major', 'degree', 'start', 'end'] as const;
const AUTOFILL_EXPERIENCE_KEYS = ['company', 'position', 'start', 'end', 'description'] as const;
const AUTOFILL_PROJECT_KEYS = ['name', 'role', 'start', 'end', 'description'] as const;

function isResumeImportParse(value: unknown): value is ResumeImportParseResponse {
  if (
    !isRecordWithKeys(value, [
      'fileType',
      'extractedText',
      'blocks',
      'sections',
      'profileCandidates',
      'warnings',
      'metrics',
    ]) ||
    (value.fileType !== 'PDF' && value.fileType !== 'DOCX') ||
    typeof value.extractedText !== 'string' ||
    !Array.isArray(value.blocks) ||
    !value.blocks.every(
      (item) =>
        isRecordWithKeys(item, ['kind', 'text']) &&
        (item.kind === 'TEXT' || item.kind === 'TABLE_ROW' || item.kind === 'HEADING') &&
        typeof item.text === 'string',
    ) ||
    !Array.isArray(value.sections) ||
    !value.sections.every(isResumeImportSection) ||
    !Array.isArray(value.warnings) ||
    !value.warnings.every(
      (item) =>
        isRecordWithKeys(item, ['code', 'message']) &&
        typeof item.code === 'string' &&
        typeof item.message === 'string',
    ) ||
    !isResumeImportProfileCandidates(value.profileCandidates) ||
    !isResumeImportMetrics(value.metrics)
  ) {
    return false;
  }
  return true;
}

function isResumeImportSection(value: unknown): boolean {
  return (
    isRecordWithKeys(value, ['type', 'heading', 'text']) &&
    [
      'BASIC',
      'EDUCATION',
      'EXPERIENCE',
      'PROJECT',
      'SKILLS',
      'CERTIFICATES',
      'AWARDS',
      'OTHER',
    ].includes(value.type as string) &&
    isNullableString(value.heading) &&
    typeof value.text === 'string'
  );
}

function isResumeImportProfileCandidates(value: unknown): boolean {
  return (
    isRecordWithKeys(value, ['personal', 'education', 'experience', 'projects', 'links']) &&
    isRecordWithKeys(value.personal, ['name', 'phone', 'email', 'currentCity']) &&
    Object.values(value.personal).every(isNullableString) &&
    Array.isArray(value.education) &&
    value.education.every(
      (item) =>
        isRecordWithKeys(item, AUTOFILL_EDUCATION_KEYS) &&
        isNullableString(item.school) &&
        isNullableString(item.major) &&
        isNullableString(item.degree) &&
        isNullableMonth(item.start) &&
        isNullableMonth(item.end),
    ) &&
    Array.isArray(value.experience) &&
    value.experience.every(
      (item) =>
        isRecordWithKeys(item, AUTOFILL_EXPERIENCE_KEYS) &&
        isNullableString(item.company) &&
        isNullableString(item.position) &&
        isNullableMonth(item.start) &&
        isNullableMonth(item.end) &&
        isNullableString(item.description),
    ) &&
    Array.isArray(value.projects) &&
    value.projects.every(isAutofillProject) &&
    isRecordWithKeys(value.links, ['github', 'portfolio', 'homepage']) &&
    Object.values(value.links).every(isNullableHttpUrl)
  );
}

function isResumeImportMetrics(value: unknown): boolean {
  return (
    isRecordWithKeys(value, [
      'fileSizeBytes',
      'pageCount',
      'parseLatencyMs',
      'extractedCharacterCount',
    ]) &&
    isNonNegativeInteger(value.fileSizeBytes) &&
    (value.pageCount === null || isNonNegativeInteger(value.pageCount)) &&
    isNonNegativeInteger(value.parseLatencyMs) &&
    isNonNegativeInteger(value.extractedCharacterCount)
  );
}

function isAutofillProfile(value: unknown): boolean {
  return (
    isRecordWithKeys(value, [
      'personal',
      'education',
      'experience',
      'projects',
      'links',
      'createdAt',
      'updatedAt',
    ]) &&
    isRecordWithKeys(value.personal, ['name', 'phone', 'email', 'currentCity']) &&
    Object.values(value.personal).every(isNullableString) &&
    Array.isArray(value.education) &&
    value.education.length <= 20 &&
    value.education.every(
      (item) =>
        isRecordWithKeys(item, AUTOFILL_EDUCATION_KEYS) &&
        isNullableString(item.school) &&
        isNullableString(item.major) &&
        isNullableString(item.degree) &&
        isNullableMonth(item.start) &&
        isNullableMonth(item.end),
    ) &&
    Array.isArray(value.experience) &&
    value.experience.length <= 20 &&
    value.experience.every(
      (item) =>
        isRecordWithKeys(item, AUTOFILL_EXPERIENCE_KEYS) &&
        isNullableString(item.company) &&
        isNullableString(item.position) &&
        isNullableMonth(item.start) &&
        isNullableMonth(item.end) &&
        isNullableString(item.description),
    ) &&
    Array.isArray(value.projects) &&
    value.projects.length <= 20 &&
    value.projects.every(isAutofillProject) &&
    isRecordWithKeys(value.links, ['github', 'portfolio', 'homepage']) &&
    Object.values(value.links).every(isNullableHttpUrl) &&
    isDateString(value.createdAt) &&
    isDateString(value.updatedAt)
  );
}

function isAutofillProject(value: unknown): boolean {
  return (
    isRecordWithKeys(value, AUTOFILL_PROJECT_KEYS) &&
    isNullableString(value.name) &&
    isNullableString(value.role) &&
    isNullableMonth(value.start) &&
    isNullableMonth(value.end) &&
    isNullableString(value.description)
  );
}

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
    isNullableString(value.outcomeNote) &&
    (value.rejectionReason === null || isRejectionReason(value.rejectionReason)) &&
    (value.appliedAt === null || isDateString(value.appliedAt)) &&
    isDateString(value.createdAt) &&
    isDateString(value.updatedAt)
  );
}

function isInterviewQuestion(value: unknown): value is InterviewQuestion {
  return (
    isRecordWithKeys(value, INTERVIEW_QUESTION_KEYS) &&
    typeof value.id === 'string' &&
    typeof value.interviewRoundId === 'string' &&
    typeof value.question === 'string' &&
    isQuestionCategory(value.category) &&
    isNullableString(value.answerSummary) &&
    isQuestionPerformance(value.performance) &&
    isNullableString(value.note) &&
    isDateString(value.createdAt) &&
    isDateString(value.updatedAt)
  );
}

function isInterviewRound(value: unknown): value is InterviewRound {
  return (
    isRecordWithKeys(value, INTERVIEW_ROUND_KEYS) &&
    typeof value.id === 'string' &&
    typeof value.applicationId === 'string' &&
    typeof value.roundName === 'string' &&
    isInterviewType(value.interviewType) &&
    (value.scheduledAt === null || isDateString(value.scheduledAt)) &&
    isInterviewStatus(value.status) &&
    isNullableString(value.interviewerNote) &&
    isNullableString(value.wentWell) &&
    isNullableString(value.couldImprove) &&
    isNullableString(value.learningNotes) &&
    isNullableString(value.otherNotes) &&
    Array.isArray(value.questions) &&
    value.questions.every(isInterviewQuestion) &&
    isDateString(value.createdAt) &&
    isDateString(value.updatedAt)
  );
}

function isFeedbackSummary(value: unknown): value is FeedbackSummary {
  return (
    isRecordWithKeys(value, [
      'hasData',
      'totals',
      'funnel',
      'questionCategories',
      'performances',
      'weakCategories',
      'rejectionReasons',
      'unrecordedRejectionReasons',
      'resumeVersions',
      'sources',
    ]) &&
    typeof value.hasData === 'boolean' &&
    isFeedbackTotals(value.totals) &&
    Array.isArray(value.funnel) &&
    value.funnel.every(
      (item) =>
        isRecordWithKeys(item, ['stage', 'count', 'conversionRate']) &&
        isFunnelStage(item.stage) &&
        isNonNegativeInteger(item.count) &&
        (item.conversionRate === null || isNonNegativeNumber(item.conversionRate)),
    ) &&
    Array.isArray(value.questionCategories) &&
    value.questionCategories.every(
      (item) =>
        isRecordWithKeys(item, ['category', 'count']) &&
        isQuestionCategory(item.category) &&
        isNonNegativeInteger(item.count),
    ) &&
    Array.isArray(value.performances) &&
    value.performances.every(
      (item) =>
        isRecordWithKeys(item, ['performance', 'count']) &&
        isQuestionPerformance(item.performance) &&
        isNonNegativeInteger(item.count),
    ) &&
    Array.isArray(value.weakCategories) &&
    value.weakCategories.every(
      (item) =>
        isRecordWithKeys(item, ['category', 'questionCount', 'weakCount']) &&
        isQuestionCategory(item.category) &&
        isNonNegativeInteger(item.questionCount) &&
        isNonNegativeInteger(item.weakCount),
    ) &&
    Array.isArray(value.rejectionReasons) &&
    value.rejectionReasons.every(
      (item) =>
        isRecordWithKeys(item, ['reason', 'count']) &&
        isRejectionReason(item.reason) &&
        isNonNegativeInteger(item.count),
    ) &&
    isNonNegativeInteger(value.unrecordedRejectionReasons) &&
    Array.isArray(value.resumeVersions) &&
    value.resumeVersions.every(isResumeVersionFeedbackStats) &&
    Array.isArray(value.sources) &&
    value.sources.every(isSourceFeedbackStats)
  );
}

function isFeedbackTotals(value: unknown): boolean {
  return (
    isRecordWithKeys(value, [
      'savedJobs',
      'applications',
      'interviewApplications',
      'interviews',
      'questions',
      'offers',
      'rejected',
    ]) && Object.values(value).every(isNonNegativeInteger)
  );
}

function isResumeVersionFeedbackStats(value: unknown): boolean {
  return (
    isRecordWithKeys(value, [
      'resumeVersionId',
      'resumeVersionName',
      'applications',
      'interviewApplications',
      'offers',
    ]) &&
    typeof value.resumeVersionId === 'string' &&
    typeof value.resumeVersionName === 'string' &&
    isFeedbackGroupStats(value)
  );
}

function isSourceFeedbackStats(value: unknown): boolean {
  return (
    isRecordWithKeys(value, ['source', 'applications', 'interviewApplications', 'offers']) &&
    (value.source === 'manual' || value.source === 'boss' || value.source === 'nowcoder') &&
    isFeedbackGroupStats(value)
  );
}

function isFeedbackGroupStats(value: Record<string, unknown>): boolean {
  return (
    isNonNegativeInteger(value.applications) &&
    isNonNegativeInteger(value.interviewApplications) &&
    isNonNegativeInteger(value.offers)
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

function isNullableMonth(value: unknown): boolean {
  return value === null || (typeof value === 'string' && /^[0-9]{4}-(0[1-9]|1[0-2])$/.test(value));
}

function isNullableHttpUrl(value: unknown): boolean {
  if (value === null) return true;
  if (typeof value !== 'string') return false;
  try {
    const parsed = new URL(value);
    return (
      (parsed.protocol === 'http:' || parsed.protocol === 'https:') &&
      !parsed.username &&
      !parsed.password
    );
  } catch {
    return false;
  }
}

function isApplicationStatus(value: unknown): value is ApplicationStatus {
  return typeof value === 'string' && APPLICATION_STATUSES.has(value as ApplicationStatus);
}

function isRejectionReason(value: unknown): boolean {
  return (
    value === 'TECHNICAL' ||
    value === 'EXPERIENCE' ||
    value === 'PRODUCT' ||
    value === 'BUSINESS' ||
    value === 'COMMUNICATION' ||
    value === 'ROLE_FIT' ||
    value === 'HEADCOUNT' ||
    value === 'UNKNOWN' ||
    value === 'OTHER'
  );
}

function isInterviewType(value: unknown): boolean {
  return value === 'PHONE' || value === 'VIDEO' || value === 'ONSITE' || value === 'OTHER';
}

function isInterviewStatus(value: unknown): boolean {
  return value === 'PLANNED' || value === 'COMPLETED' || value === 'CANCELLED';
}

function isQuestionCategory(value: unknown): boolean {
  return (
    value === 'PRODUCT' ||
    value === 'AI' ||
    value === 'TECHNICAL' ||
    value === 'PROJECT' ||
    value === 'BEHAVIORAL' ||
    value === 'BUSINESS' ||
    value === 'OTHER'
  );
}

function isQuestionPerformance(value: unknown): boolean {
  return value === 'GOOD' || value === 'OK' || value === 'POOR' || value === 'NOT_SURE';
}

function isFunnelStage(value: unknown): boolean {
  return (
    value === 'SAVED_JOBS' ||
    value === 'APPLICATIONS' ||
    value === 'INTERVIEW_APPLICATIONS' ||
    value === 'OFFERS'
  );
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0;
}

function isNonNegativeNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

function isLoopbackHostname(hostname: string): boolean {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]';
}
