import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type {
  ApiClient,
  Application,
  CreateJobInput,
  Job,
  JobAnalysisResponse,
  JobListItem,
} from '@jobpilot/api-client';

import { App } from './App';

const healthyResponse = { status: 'ok', service: 'jobpilot-api' } as const;

afterEach(() => {
  cleanup();
  window.history.replaceState(null, '', '/');
});

describe('App', () => {
  it('renders a clear checking state while the local API health request is pending', () => {
    const apiClient = createApiClient({
      getHealth: vi.fn(() => new Promise<never>(() => undefined)),
    });

    render(<App apiClient={apiClient} />);

    expect(screen.getByRole('heading', { name: 'JobPilot' })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('正在连接本地服务');
    expect(screen.getByRole('status')).toHaveAttribute('aria-busy', 'true');
  });

  it('renders API unavailable with a working retry', async () => {
    const getHealth = vi
      .fn<ApiClient['getHealth']>()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(healthyResponse);
    const apiClient = createApiClient({ getHealth });

    render(<App apiClient={apiClient} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('无法连接本地服务');

    fireEvent.click(screen.getByRole('button', { name: '重试' }));

    expect(await screen.findByRole('heading', { name: '岗位库' })).toBeInTheDocument();
    expect(getHealth).toHaveBeenCalledTimes(2);
  });

  it('shows the actionable empty job library', async () => {
    render(<App apiClient={createApiClient()} />);

    expect(await screen.findByRole('heading', { name: '岗位库' })).toBeInTheDocument();
    expect(await screen.findByText('还没有保存岗位')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '添加岗位' })).toBeEnabled();
  });

  it('lists captured BOSS jobs with their source label', async () => {
    const bossJob = createJob({
      source: 'boss',
      sourceUrl: 'https://www.zhipin.com/job_detail/fixture123.html',
    });
    const listJobs = vi.fn().mockResolvedValue(page([{ ...bossJob, applicationStatus: null }]));

    render(<App apiClient={createApiClient({ listJobs })} />);

    expect(await screen.findByText('BOSS直聘')).toBeInTheDocument();
    expect(listJobs).toHaveBeenCalledWith({});
  });

  it('lists captured Nowcoder jobs with their source label', async () => {
    const nowcoderJob = createJob({
      source: 'nowcoder',
      sourceUrl: 'https://www.nowcoder.com/jobs/detail/448241',
    });
    const listJobs = vi.fn().mockResolvedValue(page([{ ...nowcoderJob, applicationStatus: null }]));

    render(<App apiClient={createApiClient({ listJobs })} />);

    expect(await screen.findByText('牛客')).toBeInTheDocument();
    expect(listJobs).toHaveBeenCalledWith({});
  });

  it('opens a local Job detail deep link without loading the library first', async () => {
    const jobId = '11111111-1111-4111-8111-111111111111';
    const bossJob = { ...createJob({ source: 'boss' }), id: jobId };
    const apiClient = createApiClient({ getJob: vi.fn().mockResolvedValue(bossJob) });
    window.history.replaceState(null, '', `/?jobId=${jobId}`);

    render(<App apiClient={apiClient} />);

    expect(await screen.findByRole('heading', { name: bossJob.title })).toBeInTheDocument();
    expect(screen.getAllByText('BOSS直聘').length).toBeGreaterThan(0);
    expect(apiClient.getJob).toHaveBeenCalledWith(jobId);
    expect(apiClient.listJobs).not.toHaveBeenCalled();
  });

  it('opens the manual add form from its local fallback deep link', async () => {
    window.history.replaceState(null, '', '/?view=create');

    render(<App apiClient={createApiClient()} />);

    expect(await screen.findByRole('heading', { name: '添加岗位' })).toBeInTheDocument();
  });

  it('adds a manual job and opens its detail', async () => {
    const apiClient = createStatefulApiClient();
    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '添加岗位' }));
    fireEvent.change(screen.getByLabelText('职位名称 *'), {
      target: { value: 'AI 产品经理实习生' },
    });
    fireEvent.change(screen.getByLabelText('公司 *'), { target: { value: '测试公司' } });
    fireEvent.change(screen.getByLabelText('岗位链接'), {
      target: { value: 'https://example.com/jobs/ai-pm' },
    });
    fireEvent.change(screen.getByLabelText('JD'), {
      target: { value: '负责 AI 产品设计与需求分析' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存岗位' }));

    expect(await screen.findByRole('heading', { name: 'AI 产品经理实习生' })).toBeInTheDocument();
    expect(screen.getByText('负责 AI 产品设计与需求分析')).toBeInTheDocument();
    expect(apiClient.createJob).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'AI 产品经理实习生',
        company: '测试公司',
        source: 'manual',
      }),
    );
  });

  it('validates required fields and source URL before calling the API', async () => {
    const apiClient = createApiClient();
    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '添加岗位' }));
    fireEvent.change(screen.getByLabelText('岗位链接'), {
      target: { value: 'ftp://example.com/job' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存岗位' }));

    expect(screen.getByRole('alert')).toHaveTextContent('请填写职位名称和公司');
    expect(apiClient.createJob).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('职位名称 *'), { target: { value: '岗位' } });
    fireEvent.change(screen.getByLabelText('公司 *'), { target: { value: '公司' } });
    fireEvent.click(screen.getByRole('button', { name: '保存岗位' }));

    expect(screen.getByRole('alert')).toHaveTextContent('HTTP 或 HTTPS');
    expect(apiClient.createJob).not.toHaveBeenCalled();
  });

  it('opens the original-platform URL without mutating application state', async () => {
    const job = createJob();
    const apiClient = createApiClient({
      listJobs: vi.fn().mockResolvedValue(page([{ ...job, applicationStatus: null }])),
      getJob: vi.fn().mockResolvedValue(job),
    });
    render(<App apiClient={apiClient} />);

    fireEvent.click(await screen.findByRole('button', { name: '查看详情' }));
    const link = await screen.findByRole('link', { name: '去原平台查看/投递' });

    expect(link).toHaveAttribute('href', 'https://example.com/jobs/ai-pm');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noreferrer');
    expect(apiClient.createApplication).not.toHaveBeenCalled();
    expect(apiClient.updateApplication).not.toHaveBeenCalled();
  });

  it('preserves a captured Job source when editing its snapshot', async () => {
    const bossJob = createJob({
      source: 'boss',
      sourceUrl: 'https://www.zhipin.com/job_detail/fixture123.html',
    });
    const updateJob = vi.fn().mockResolvedValue(bossJob);
    const apiClient = createApiClient({
      listJobs: vi.fn().mockResolvedValue(page([{ ...bossJob, applicationStatus: null }])),
      getJob: vi.fn().mockResolvedValue(bossJob),
      updateJob,
    });
    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看详情' }));
    fireEvent.click(await screen.findByRole('button', { name: '编辑岗位' }));
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }));

    expect(updateJob).toHaveBeenCalledWith(bossJob.id, expect.objectContaining({ source: 'boss' }));
  });

  it('loads only the application for the opened job', async () => {
    const job = createJob();
    const apiClient = createApiClient({
      listJobs: vi.fn().mockResolvedValue(page([{ ...job, applicationStatus: 'planned' }])),
      getJob: vi.fn().mockResolvedValue(job),
    });
    render(<App apiClient={apiClient} />);

    fireEvent.click(await screen.findByRole('button', { name: '查看详情' }));
    await screen.findByRole('heading', { name: 'AI 产品经理实习生' });

    expect(apiClient.listApplications).toHaveBeenCalledWith({ jobId: 'job-1', limit: 1 });
  });

  it('shows unconfigured AI without hiding or blocking the original JD', async () => {
    const job = createJob();
    const apiClient = createApiClient({
      listJobs: vi.fn().mockResolvedValue(page([{ ...job, applicationStatus: null }])),
      getJob: vi.fn().mockResolvedValue(job),
      getJobAnalysis: vi.fn().mockResolvedValue({ isConfigured: false, analysis: null }),
    });
    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看详情' }));

    expect(await screen.findByText('AI 服务未配置')).toBeInTheDocument();
    expect(screen.getByText('负责 AI 产品设计与需求分析')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'AI 分析此岗位' })).toBeNull();
  });

  it('shows analysis progress, structured fields and lightweight evidence', async () => {
    const job = createJob();
    let resolveAnalysis: ((value: JobAnalysisResponse) => void) | undefined;
    const analysisRequest = new Promise<JobAnalysisResponse>((resolve) => {
      resolveAnalysis = resolve;
    });
    const apiClient = createApiClient({
      listJobs: vi.fn().mockResolvedValue(page([{ ...job, applicationStatus: null }])),
      getJob: vi.fn().mockResolvedValue(job),
      getJobAnalysis: vi.fn().mockResolvedValue({ isConfigured: true, analysis: null }),
      analyzeJob: vi.fn().mockReturnValue(analysisRequest),
    });
    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看详情' }));
    fireEvent.click(await screen.findByRole('button', { name: 'AI 分析此岗位' }));

    expect(screen.getByRole('button', { name: '分析中…' })).toBeDisabled();
    await act(async () => {
      resolveAnalysis?.(createAnalysisResponse());
      await analysisRequest;
    });

    expect(screen.getByText('聚焦 AI 产品需求与方案设计。')).toBeInTheDocument();
    expect(screen.getByText('负责产品设计')).toBeInTheDocument();
    expect(screen.getByText('需求分析', { selector: '.analysis-tag' })).toBeInTheDocument();
    expect(screen.getByText('准备说明产品设计方法')).toBeInTheDocument();
    expect(screen.getAllByText('查看原文依据').length).toBeGreaterThan(0);
    expect(screen.getByText('负责 AI 产品设计与需求分析')).toBeInTheDocument();
    expect(apiClient.analyzeJob).toHaveBeenCalledWith(job.id);
  });

  it('retains a stale result and offers explicit reanalysis', async () => {
    const job = createJob();
    const stale = createAnalysisResponse();
    if (stale.analysis) stale.analysis.isStale = true;
    const apiClient = createApiClient({
      listJobs: vi.fn().mockResolvedValue(page([{ ...job, applicationStatus: null }])),
      getJob: vi.fn().mockResolvedValue(job),
      getJobAnalysis: vi.fn().mockResolvedValue(stale),
    });
    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看详情' }));

    expect(await screen.findByText('岗位信息已修改，当前分析可能已过期。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重新分析' })).toBeEnabled();
    expect(screen.getByText('聚焦 AI 产品需求与方案设计。')).toBeInTheDocument();
  });

  it('shows a bounded analysis failure while the Job detail remains usable', async () => {
    const job = createJob();
    const apiClient = createApiClient({
      listJobs: vi.fn().mockResolvedValue(page([{ ...job, applicationStatus: null }])),
      getJob: vi.fn().mockResolvedValue(job),
      getJobAnalysis: vi.fn().mockResolvedValue({ isConfigured: true, analysis: null }),
      analyzeJob: vi.fn().mockRejectedValue(new Error('raw provider response and secret')),
    });
    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看详情' }));
    fireEvent.click(await screen.findByRole('button', { name: 'AI 分析此岗位' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('AI 分析暂时不可用，请稍后重试。');
    expect(screen.getByText('负责 AI 产品设计与需求分析')).toBeInTheDocument();
    expect(screen.queryByText('raw provider response and secret')).toBeNull();
  });

  it('creates an application and explicitly confirms applied status', async () => {
    const job = createJob();
    let application: Application | undefined;
    const apiClient = createApiClient({
      listJobs: vi.fn().mockResolvedValue(page([{ ...job, applicationStatus: null }])),
      getJob: vi.fn().mockResolvedValue(job),
      listApplications: vi.fn(async () =>
        page(application ? [{ ...application, jobTitle: job.title, company: job.company }] : []),
      ),
      createApplication: vi.fn(async () => {
        application = createApplication('planned');
        return application;
      }),
      updateApplication: vi.fn(async (_id, input) => {
        application = createApplication(input.status);
        return application;
      }),
    });
    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看详情' }));

    fireEvent.click(await screen.findByRole('button', { name: '建立投递' }));
    expect((await screen.findAllByText('计划投递')).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: '我已完成投递' }));

    expect((await screen.findAllByText('已投递')).length).toBeGreaterThan(0);
    expect(screen.getByRole('combobox', { name: '更正或推进状态' })).toHaveValue('applied');
    expect(apiClient.updateApplication).toHaveBeenCalledWith('application-1', {
      status: 'applied',
      confirmApplied: true,
    });
  });

  it('ignores a stale health failure after the API client changes', async () => {
    let rejectStaleRequest: ((reason?: unknown) => void) | undefined;
    const staleRequest = new Promise<never>((_resolve, reject) => {
      rejectStaleRequest = reject;
    });
    const staleClient = createApiClient({ getHealth: vi.fn().mockReturnValue(staleRequest) });
    const currentClient = createApiClient();
    const { rerender } = render(<App apiClient={staleClient} />);

    rerender(<App apiClient={currentClient} />);
    expect(await screen.findByRole('heading', { name: '岗位库' })).toBeInTheDocument();

    await act(async () => {
      rejectStaleRequest?.(new Error('stale failure'));
      await staleRequest.catch(() => undefined);
    });

    expect(screen.queryByRole('alert')).toBeNull();
  });
});

function createApiClient(overrides: Partial<ApiClient> = {}): ApiClient {
  return {
    getHealth: vi.fn().mockResolvedValue(healthyResponse),
    createJob: vi.fn(),
    listJobs: vi.fn().mockResolvedValue(page([])),
    getJob: vi.fn(),
    updateJob: vi.fn(),
    deleteJob: vi.fn(),
    createApplication: vi.fn(),
    listApplications: vi.fn().mockResolvedValue(page([])),
    getApplication: vi.fn(),
    updateApplication: vi.fn(),
    getJobAnalysis: vi.fn().mockResolvedValue({ isConfigured: false, analysis: null }),
    analyzeJob: vi.fn(),
    ...overrides,
  };
}

function createStatefulApiClient(): ApiClient {
  let jobs: JobListItem[] = [];
  const client = createApiClient();
  client.listJobs = vi.fn(async () => page(jobs));
  client.createJob = vi.fn(async (input: CreateJobInput) => {
    const job = createJob(input);
    jobs = [{ ...job, applicationStatus: null }];
    client.getJob = vi.fn().mockResolvedValue(job);
    return job;
  });
  return client;
}

function createJob(input: Partial<CreateJobInput> = {}): Job {
  return {
    id: 'job-1',
    title: input.title ?? 'AI 产品经理实习生',
    company: input.company ?? '测试公司',
    location: input.location ?? '上海',
    salaryText: input.salaryText ?? '200-300/天',
    source: input.source ?? 'manual',
    sourceUrl: input.sourceUrl ?? 'https://example.com/jobs/ai-pm',
    description: input.description ?? '负责 AI 产品设计与需求分析',
    notes: input.notes ?? null,
    createdAt: '2026-09-03T00:00:00Z',
    updatedAt: '2026-09-03T00:00:00Z',
  };
}

function createApplication(status: Application['status']): Application {
  return {
    id: 'application-1',
    jobId: 'job-1',
    status,
    appliedAt: status === 'applied' ? '2026-09-03T00:01:00Z' : null,
    createdAt: '2026-09-03T00:00:00Z',
    updatedAt: '2026-09-03T00:01:00Z',
  };
}

function page<T>(items: T[]) {
  return { items, total: items.length, limit: 50, offset: 0 };
}

function createAnalysisResponse(): JobAnalysisResponse {
  return {
    isConfigured: true,
    analysis: {
      id: 'analysis-1',
      jobId: 'job-1',
      schemaVersion: 1,
      result: {
        summary: '聚焦 AI 产品需求与方案设计。',
        responsibilities: [{ text: '负责产品设计', evidence: '负责 AI 产品设计' }],
        mustHaveRequirements: [{ text: '能够分析需求', evidence: '需求分析' }],
        preferredRequirements: [],
        skills: ['需求分析'],
        experienceRequirements: [],
        educationRequirements: [],
        domainKeywords: ['AI 产品'],
        interviewFocus: [{ text: '准备说明产品设计方法', evidence: 'AI 产品设计' }],
      },
      isStale: false,
      createdAt: '2026-09-04T00:00:00Z',
      updatedAt: '2026-09-04T00:00:00Z',
    },
  };
}
