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
  status: ApplicationStatus;
  confirmApplied: boolean;
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    requestId: string;
    resourceId?: string;
  };
}
