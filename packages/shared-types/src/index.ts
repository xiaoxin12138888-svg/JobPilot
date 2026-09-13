export interface ApiHealthResponse {
  status: 'ok';
  service: 'jobpilot-api';
}

export type JobSource = 'manual' | 'boss' | 'nowcoder';

export const JOB_SOURCE_LABELS: Readonly<Record<JobSource, string>> = {
  manual: '手动录入',
  boss: 'BOSS直聘',
  nowcoder: '牛客',
};

export type ApplicationStatus =
  | 'planned'
  | 'applied'
  | 'screening'
  | 'assessment'
  | 'interviewing'
  | 'offer'
  | 'rejected'
  | 'withdrawn'
  | 'closed';

export const APPLICATION_STATUS_LABELS: Readonly<Record<ApplicationStatus, string>> = {
  planned: '计划投递',
  applied: '已投递',
  screening: '筛选中',
  assessment: '笔试/测评',
  interviewing: '面试中',
  offer: 'Offer',
  rejected: '淘汰',
  withdrawn: '已放弃',
  closed: '岗位关闭',
};

export type RejectionReason =
  | 'TECHNICAL'
  | 'EXPERIENCE'
  | 'PRODUCT'
  | 'BUSINESS'
  | 'COMMUNICATION'
  | 'ROLE_FIT'
  | 'HEADCOUNT'
  | 'UNKNOWN'
  | 'OTHER';

export const REJECTION_REASON_LABELS: Readonly<Record<RejectionReason, string>> = {
  TECHNICAL: '技术能力',
  EXPERIENCE: '经验匹配',
  PRODUCT: '产品能力',
  BUSINESS: '业务理解',
  COMMUNICATION: '沟通表达',
  ROLE_FIT: '岗位匹配',
  HEADCOUNT: '岗位名额',
  UNKNOWN: '未知',
  OTHER: '其他',
};

export type InterviewType = 'PHONE' | 'VIDEO' | 'ONSITE' | 'OTHER';
export type InterviewStatus = 'PLANNED' | 'COMPLETED' | 'CANCELLED';
export type QuestionCategory =
  'PRODUCT' | 'AI' | 'TECHNICAL' | 'PROJECT' | 'BEHAVIORAL' | 'BUSINESS' | 'OTHER';
export type QuestionPerformance = 'GOOD' | 'OK' | 'POOR' | 'NOT_SURE';

export const INTERVIEW_TYPE_LABELS: Readonly<Record<InterviewType, string>> = {
  PHONE: '电话',
  VIDEO: '视频',
  ONSITE: '现场',
  OTHER: '其他',
};

export const INTERVIEW_STATUS_LABELS: Readonly<Record<InterviewStatus, string>> = {
  PLANNED: '待进行',
  COMPLETED: '已完成',
  CANCELLED: '已取消',
};

export const QUESTION_CATEGORY_LABELS: Readonly<Record<QuestionCategory, string>> = {
  PRODUCT: '产品',
  AI: 'AI',
  TECHNICAL: '技术',
  PROJECT: '项目',
  BEHAVIORAL: '行为',
  BUSINESS: '业务',
  OTHER: '其他',
};

export const QUESTION_PERFORMANCE_LABELS: Readonly<Record<QuestionPerformance, string>> = {
  GOOD: '答得较好',
  OK: '一般',
  POOR: '答得不好',
  NOT_SURE: '不确定',
};

export interface Job {
  id: string;
  title: string;
  company: string;
  location: string | null;
  salaryText: string | null;
  source: JobSource;
  sourceUrl: string | null;
  description: string | null;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface JobListItem extends Job {
  applicationStatus: ApplicationStatus | null;
}

export interface JobListResponse {
  items: JobListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface CreateJobInput {
  title: string;
  company: string;
  location?: string | null;
  salaryText?: string | null;
  source?: JobSource;
  sourceUrl?: string | null;
  description?: string | null;
  notes?: string | null;
}

export type UpdateJobInput = Partial<CreateJobInput>;

export interface Application {
  id: string;
  jobId: string;
  status: ApplicationStatus;
  resumeVersionId: string | null;
  outcomeNote: string | null;
  rejectionReason: RejectionReason | null;
  appliedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ApplicationListItem extends Application {
  jobTitle: string;
  company: string;
}

export interface ApplicationListResponse {
  items: ApplicationListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface UpdateApplicationInput {
  status?: ApplicationStatus;
  confirmApplied?: boolean;
  resumeVersionId?: string | null;
  outcomeNote?: string | null;
  rejectionReason?: RejectionReason | null;
}

export interface InterviewQuestion {
  id: string;
  interviewRoundId: string;
  question: string;
  category: QuestionCategory;
  answerSummary: string | null;
  performance: QuestionPerformance;
  note: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface InterviewRound {
  id: string;
  applicationId: string;
  roundName: string;
  interviewType: InterviewType;
  scheduledAt: string | null;
  status: InterviewStatus;
  interviewerNote: string | null;
  wentWell: string | null;
  couldImprove: string | null;
  learningNotes: string | null;
  otherNotes: string | null;
  questions: InterviewQuestion[];
  createdAt: string;
  updatedAt: string;
}

export interface InterviewRoundListResponse {
  items: InterviewRound[];
  total: number;
  limit: number;
  offset: number;
}

export interface CreateInterviewRoundInput {
  roundName: string;
  interviewType: InterviewType;
  scheduledAt?: string | null;
  status?: InterviewStatus;
  interviewerNote?: string | null;
  wentWell?: string | null;
  couldImprove?: string | null;
  learningNotes?: string | null;
  otherNotes?: string | null;
}

export type UpdateInterviewRoundInput = Partial<CreateInterviewRoundInput>;

export interface CreateInterviewQuestionInput {
  question: string;
  category: QuestionCategory;
  answerSummary?: string | null;
  performance?: QuestionPerformance;
  note?: string | null;
}

export type UpdateInterviewQuestionInput = Partial<CreateInterviewQuestionInput>;

export type FunnelStageName = 'SAVED_JOBS' | 'APPLICATIONS' | 'INTERVIEW_APPLICATIONS' | 'OFFERS';

export interface FeedbackTotals {
  savedJobs: number;
  applications: number;
  interviewApplications: number;
  interviews: number;
  questions: number;
  offers: number;
  rejected: number;
}

export interface FunnelStage {
  stage: FunnelStageName;
  count: number;
  conversionRate: number | null;
}

export interface FeedbackGroupStats {
  applications: number;
  interviewApplications: number;
  offers: number;
}

export interface SourceFeedbackStats extends FeedbackGroupStats {
  source: JobSource;
}

export interface ResumeVersionFeedbackStats extends FeedbackGroupStats {
  resumeVersionId: string;
  resumeVersionName: string;
}

export interface FeedbackSummary {
  hasData: boolean;
  totals: FeedbackTotals;
  funnel: FunnelStage[];
  questionCategories: { category: QuestionCategory; count: number }[];
  performances: { performance: QuestionPerformance; count: number }[];
  weakCategories: {
    category: QuestionCategory;
    questionCount: number;
    weakCount: number;
  }[];
  rejectionReasons: { reason: RejectionReason; count: number }[];
  unrecordedRejectionReasons: number;
  resumeVersions: ResumeVersionFeedbackStats[];
  sources: SourceFeedbackStats[];
}

export interface ResumeVersion {
  id: string;
  name: string;
  content: string;
  applicationCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface ResumeVersionListResponse {
  items: ResumeVersion[];
  total: number;
  limit: number;
  offset: number;
}

export interface AutofillPersonalDetails {
  name: string | null;
  phone: string | null;
  email: string | null;
  currentCity: string | null;
}

export interface AutofillEducationEntry {
  school: string | null;
  major: string | null;
  degree: string | null;
  start: string | null;
  end: string | null;
}

export interface AutofillExperienceEntry {
  company: string | null;
  position: string | null;
  start: string | null;
  end: string | null;
  description: string | null;
}

export interface AutofillProjectEntry {
  name: string | null;
  role: string | null;
  start: string | null;
  end: string | null;
  description: string | null;
}

export interface AutofillProfileLinks {
  github: string | null;
  portfolio: string | null;
  homepage: string | null;
}

export interface AutofillProfileInput {
  personal: AutofillPersonalDetails;
  education: AutofillEducationEntry[];
  experience: AutofillExperienceEntry[];
  projects: AutofillProjectEntry[];
  links: AutofillProfileLinks;
}

export interface AutofillProfile extends AutofillProfileInput {
  createdAt: string;
  updatedAt: string;
}

export interface AutofillProfileResponse {
  profile: AutofillProfile | null;
}

export type ResumeImportFileType = 'PDF' | 'DOCX';
export type ResumeImportBlockKind = 'TEXT' | 'TABLE_ROW' | 'HEADING';
export type ResumeImportSectionKind =
  'BASIC' | 'EDUCATION' | 'EXPERIENCE' | 'PROJECT' | 'SKILLS' | 'CERTIFICATES' | 'AWARDS' | 'OTHER';

export interface ResumeImportBlock {
  kind: ResumeImportBlockKind;
  text: string;
}

export interface ResumeImportSection {
  type: ResumeImportSectionKind;
  heading: string | null;
  text: string;
}

export type ResumeImportEducationCandidate = AutofillEducationEntry;
export type ResumeImportExperienceCandidate = AutofillExperienceEntry;
export type ResumeImportProjectCandidate = AutofillProjectEntry;

export interface ResumeImportParseResponse {
  fileType: ResumeImportFileType;
  extractedText: string;
  blocks: ResumeImportBlock[];
  sections: ResumeImportSection[];
  profileCandidates: {
    personal: AutofillPersonalDetails;
    education: ResumeImportEducationCandidate[];
    experience: ResumeImportExperienceCandidate[];
    projects: ResumeImportProjectCandidate[];
    links: AutofillProfileLinks;
  };
  warnings: { code: string; message: string }[];
  metrics: {
    fileSizeBytes: number;
    pageCount: number | null;
    parseLatencyMs: number;
    extractedCharacterCount: number;
  };
}

export interface ResumeProfileImportInput {
  personal?: Partial<AutofillPersonalDetails>;
  education?: AutofillEducationEntry[];
  experience?: AutofillExperienceEntry[];
  projects?: AutofillProjectEntry[];
  links?: Partial<AutofillProfileLinks>;
}

export type ConfirmResumeImportInput =
  | { resumeVersion: CreateResumeVersionInput; profileImport?: ResumeProfileImportInput }
  | { resumeVersion?: CreateResumeVersionInput; profileImport: ResumeProfileImportInput };

export interface ResumeImportConfirmResponse {
  resumeVersion: ResumeVersion | null;
  profile: AutofillProfile | null;
}

export interface CreateResumeVersionInput {
  name: string;
  content: string;
}

export type UpdateResumeVersionInput = Partial<CreateResumeVersionInput>;

export interface DuplicateResumeVersionInput {
  name: string;
}

export interface EvidenceItem {
  text: string;
  evidence: string | null;
}

export interface JDAnalysis {
  summary: string;
  responsibilities: EvidenceItem[];
  mustHaveRequirements: EvidenceItem[];
  preferredRequirements: EvidenceItem[];
  skills: string[];
  experienceRequirements: EvidenceItem[];
  educationRequirements: EvidenceItem[];
  domainKeywords: string[];
  interviewFocus: EvidenceItem[];
}

export interface JDAnalysisRecord {
  id: string;
  jobId: string;
  schemaVersion: 1;
  result: JDAnalysis;
  isStale: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface JobAnalysisResponse {
  isConfigured: boolean;
  analysis: JDAnalysisRecord | null;
}

export type EvidenceRequirementType =
  'MUST_HAVE' | 'PREFERRED' | 'RESPONSIBILITY' | 'SKILL' | 'EXPERIENCE' | 'EDUCATION';
export type EvidenceCoverage = 'DIRECT' | 'PARTIAL' | 'GAP';
export type EvidenceMapSchemaVersion = 1 | 2;

export interface ResumeEvidence {
  quote: string;
}

export interface EvidenceMapping {
  requirementType: EvidenceRequirementType;
  requirementText: string;
  coverage: EvidenceCoverage;
  resumeEvidence: ResumeEvidence[];
  reason: string;
}

export interface EvidenceMap {
  mappings: EvidenceMapping[];
}

export interface EvidenceMapRecord {
  id: string;
  jobId: string;
  resumeVersionId: string;
  schemaVersion: EvidenceMapSchemaVersion;
  result: EvidenceMap;
  isStale: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface JobEvidenceMapResponse {
  isConfigured: boolean;
  evidenceMap: EvidenceMapRecord | null;
}

export type CopilotKind = 'MATCH' | 'RESUME_ADVICE' | 'INTERVIEW_PREP';
export type CopilotSourceType = 'RESUME' | 'JOB' | 'INTERVIEW';
export type CopilotInterviewCategory = 'PRODUCT' | 'AI' | 'PROJECT';

export interface CopilotSourceEvidence {
  text: string;
  sourceType: CopilotSourceType;
  sourceId: string;
}

export interface GroundedCopilotItem {
  text: string;
  sourceEvidence: CopilotSourceEvidence;
}

export interface JobMatchResult {
  summary: string;
  strengths: GroundedCopilotItem[];
  gaps: GroundedCopilotItem[];
  suggestions: string[];
}

export interface ResumeAdviceResult {
  highlight: GroundedCopilotItem[];
  possibleImprovement: string[];
  interviewFocus: GroundedCopilotItem[];
}

export interface CopilotInterviewQuestion {
  category: CopilotInterviewCategory;
  question: string;
  reason: string;
  sourceEvidence: CopilotSourceEvidence;
}

export interface CopilotInterviewReview {
  strengths: GroundedCopilotItem[];
  weaknesses: GroundedCopilotItem[];
  nextActions: string[];
}

export interface InterviewPrepResult {
  possibleQuestions: CopilotInterviewQuestion[];
  review: CopilotInterviewReview;
}

export interface CopilotRecord {
  id: string;
  jobId: string;
  resumeVersionId: string | null;
  kind: CopilotKind;
  schemaVersion: 1;
  result: JobMatchResult | ResumeAdviceResult | InterviewPrepResult;
  inputFingerprint: string;
  model: string;
  promptVersion: string;
  isStale: boolean;
  createdAt: string;
}

export interface CopilotResponse {
  isConfigured: boolean;
  record: CopilotRecord | null;
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    requestId: string;
    resourceId?: string;
  };
}
