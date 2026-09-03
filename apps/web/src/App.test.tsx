import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type {
  ApiClient,
  Application,
  CreateJobInput,
  Job,
  JobListItem,
} from '@jobpilot/api-client';

import { App } from './App';

const healthyResponse = { status: 'ok', service: 'jobpilot-api' } as const;

afterEach(cleanup);

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

  it('adds a manual job and opens its detail', async () => {
    const apiClient = createStatefulApiClient();
    render(<App apiClient={apiClient} />);
    await screen.findByRole('heading', { name: '岗位库' });

    fireEvent.click(screen.getByRole('button', { name: '添加岗位' }));
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
    await screen.findByRole('heading', { name: '岗位库' });
    fireEvent.click(screen.getByRole('button', { name: '添加岗位' }));
    fireEvent.change(screen.getByLabelText('岗位链接'), {
      target: { value: 'ftp://example.com/job' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存岗位' }));

    expect(screen.getByRole('alert')).toHaveTextContent('请填写职位名称和公司');
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
    source: 'manual',
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
