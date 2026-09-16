import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type {
  ApiClient,
  Application,
  AutofillProfile,
  CreateJobInput,
  CreateInterviewQuestionInput,
  CreateInterviewRoundInput,
  FeedbackSummary,
  InterviewQuestion,
  InterviewRound,
  Job,
  JobAnalysisResponse,
  JobListItem,
  ResumeVersion,
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

  it('shows the four AI Copilot tools on a job detail page', async () => {
    const jobId = '11111111-1111-4111-8111-111111111111';
    const job = { ...createJob(), id: jobId };
    const apiClient = createApiClient({ getJob: vi.fn().mockResolvedValue(job) });
    window.history.replaceState(null, '', `/?jobId=${jobId}`);

    render(<App apiClient={apiClient} />);

    const panel = await screen.findByRole('region', { name: 'AI 求职 Copilot' });
    for (const tool of ['岗位理解', '匹配分析', '简历准备', '面试准备']) {
      expect(within(panel).getByRole('button', { name: tool })).toBeInTheDocument();
    }
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

    const analysisPanel = screen.getByRole('region', { name: 'AI 岗位分析' });
    expect(within(analysisPanel).getByText('聚焦 AI 产品需求与方案设计。')).toBeInTheDocument();
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
    expect(
      within(screen.getByRole('region', { name: 'AI 岗位分析' })).getByText(
        '聚焦 AI 产品需求与方案设计。',
      ),
    ).toBeInTheDocument();
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

  it('keeps the last valid result visible when reanalysis fails', async () => {
    const job = createJob();
    const apiClient = createApiClient({
      listJobs: vi.fn().mockResolvedValue(page([{ ...job, applicationStatus: null }])),
      getJob: vi.fn().mockResolvedValue(job),
      getJobAnalysis: vi.fn().mockResolvedValue(createAnalysisResponse()),
      analyzeJob: vi.fn().mockRejectedValue(new Error('provider failed')),
    });
    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看详情' }));
    fireEvent.click(await screen.findByRole('button', { name: '重新分析' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('AI 分析暂时不可用，请稍后重试。');
    expect(
      within(screen.getByRole('region', { name: 'AI 岗位分析' })).getByText(
        '聚焦 AI 产品需求与方案设计。',
      ),
    ).toBeInTheDocument();
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
        application = {
          ...createApplication(input.status ?? application?.status ?? 'planned'),
          resumeVersionId: input.resumeVersionId ?? application?.resumeVersionId ?? null,
        };
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

  it('records a user-provided rejection reason and outcome note', async () => {
    const job = createJob();
    const application = createApplication('rejected');
    const updateApplication = vi.fn().mockResolvedValue({
      ...application,
      outcomeNote: '二面后未通过',
      rejectionReason: 'EXPERIENCE',
    });
    const apiClient = createApiClient({
      getJob: vi.fn().mockResolvedValue(job),
      listApplications: vi
        .fn()
        .mockResolvedValue(page([{ ...application, jobTitle: job.title, company: job.company }])),
      updateApplication,
    });
    window.history.replaceState(null, '', `/?jobId=${job.id}`);

    render(<App apiClient={apiClient} />);

    expect(
      await screen.findByText('这是你记录的已知情况或自我判断，不是系统判定。'),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('结果说明'), {
      target: { value: '二面后未通过' },
    });
    fireEvent.change(screen.getByLabelText('原因记录（由用户填写）'), {
      target: { value: 'EXPERIENCE' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存结果记录' }));

    await vi.waitFor(() =>
      expect(updateApplication).toHaveBeenCalledWith(application.id, {
        outcomeNote: '二面后未通过',
        rejectionReason: 'EXPERIENCE',
      }),
    );
    expect(await screen.findByText('结果记录已保存。')).toBeInTheDocument();
  });

  it('reuses outcome note for Offer details without a second outcome model', async () => {
    const job = createJob();
    const application = createApplication('offer');
    const updateApplication = vi.fn().mockResolvedValue({
      ...application,
      outcomeNote: '薪资已确认，10 月入职',
    });
    const apiClient = createApiClient({
      getJob: vi.fn().mockResolvedValue(job),
      listApplications: vi
        .fn()
        .mockResolvedValue(page([{ ...application, jobTitle: job.title, company: job.company }])),
      updateApplication,
    });
    window.history.replaceState(null, '', `/?jobId=${job.id}`);

    render(<App apiClient={apiClient} />);

    fireEvent.change(await screen.findByLabelText('Offer 说明'), {
      target: { value: '薪资已确认，10 月入职' },
    });
    expect(screen.queryByLabelText('原因记录（由用户填写）')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '保存结果记录' }));

    await vi.waitFor(() =>
      expect(updateApplication).toHaveBeenCalledWith(application.id, {
        outcomeNote: '薪资已确认，10 月入职',
      }),
    );
  });

  it('adds a manual interview round without changing the Application status', async () => {
    const job = createJob();
    const application = createApplication('interviewing');
    let interviews: InterviewRound[] = [];
    const createInterview = vi.fn(
      async (_applicationId: string, input: CreateInterviewRoundInput) => {
        const interview = createInterviewRound(input);
        interviews = [interview];
        return interview;
      },
    );
    const apiClient = createApiClient({
      getJob: vi.fn().mockResolvedValue(job),
      listApplications: vi
        .fn()
        .mockResolvedValue(page([{ ...application, jobTitle: job.title, company: job.company }])),
      listInterviews: vi.fn(async () => page(interviews)),
      createInterview,
    });
    window.history.replaceState(null, '', `/?jobId=${job.id}`);

    render(<App apiClient={apiClient} />);

    expect(await screen.findByText('还没有面试记录')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '添加面试' }));
    fireEvent.change(screen.getByLabelText('轮次名称 *'), { target: { value: '一面' } });
    fireEvent.change(screen.getByLabelText('面试类型'), { target: { value: 'VIDEO' } });
    fireEvent.change(screen.getByLabelText('计划时间'), {
      target: { value: '2026-09-08T14:30' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存面试' }));

    expect(await screen.findByRole('heading', { name: '一面' })).toBeInTheDocument();
    expect(createInterview).toHaveBeenCalledWith(application.id, {
      roundName: '一面',
      interviewType: 'VIDEO',
      scheduledAt: new Date('2026-09-08T14:30').toISOString(),
      interviewerNote: null,
    });
    expect(apiClient.updateApplication).not.toHaveBeenCalled();
  });

  it('edits a round self review and explicitly marks that round completed', async () => {
    const job = createJob();
    const application = createApplication('interviewing');
    let interview = createInterviewRound();
    const updateInterview = vi.fn(async (_interviewId: string, input: Partial<InterviewRound>) => {
      interview = { ...interview, ...input, updatedAt: '2026-09-06T01:00:00Z' };
      return interview;
    });
    const apiClient = createApiClient({
      getJob: vi.fn().mockResolvedValue(job),
      listApplications: vi
        .fn()
        .mockResolvedValue(page([{ ...application, jobTitle: job.title, company: job.company }])),
      listInterviews: vi.fn().mockResolvedValue(page([interview])),
      updateInterview,
    });
    window.history.replaceState(null, '', `/?jobId=${job.id}`);

    render(<App apiClient={apiClient} />);

    fireEvent.click(await screen.findByRole('button', { name: '编辑与复盘' }));
    fireEvent.change(screen.getByLabelText('轮次名称 *'), { target: { value: '产品一面' } });
    fireEvent.change(screen.getByLabelText('做得好的地方'), {
      target: { value: '结构化说明了需求拆解过程' },
    });
    fireEvent.change(screen.getByLabelText('没答好的地方'), {
      target: { value: '指标定义不够清楚' },
    });
    fireEvent.change(screen.getByLabelText('需要补充学习'), {
      target: { value: '复习北极星指标' },
    });
    fireEvent.change(screen.getByLabelText('其他备注'), {
      target: { value: '下次先确认问题范围' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存面试修改' }));

    expect(await screen.findByRole('heading', { name: '产品一面' })).toBeInTheDocument();
    expect(updateInterview).toHaveBeenCalledWith(
      interview.id,
      expect.objectContaining({
        roundName: '产品一面',
        wentWell: '结构化说明了需求拆解过程',
        couldImprove: '指标定义不够清楚',
        learningNotes: '复习北极星指标',
        otherNotes: '下次先确认问题范围',
      }),
    );

    fireEvent.click(screen.getByRole('button', { name: '标记完成' }));
    expect(await screen.findByText('已完成')).toBeInTheDocument();
    expect(updateInterview).toHaveBeenLastCalledWith(interview.id, { status: 'COMPLETED' });
    expect(apiClient.updateApplication).not.toHaveBeenCalled();
  });

  it('explicitly marks a round cancelled without changing the Application', async () => {
    const job = createJob();
    const application = createApplication('interviewing');
    let interview = createInterviewRound();
    const updateInterview = vi.fn(async (_interviewId: string, input: Partial<InterviewRound>) => {
      interview = { ...interview, ...input, updatedAt: '2026-09-06T01:00:00Z' };
      return interview;
    });
    const apiClient = createApiClient({
      getJob: vi.fn().mockResolvedValue(job),
      listApplications: vi
        .fn()
        .mockResolvedValue(page([{ ...application, jobTitle: job.title, company: job.company }])),
      listInterviews: vi.fn().mockResolvedValue(page([interview])),
      updateInterview,
    });
    window.history.replaceState(null, '', `/?jobId=${job.id}`);

    render(<App apiClient={apiClient} />);

    fireEvent.click(await screen.findByRole('button', { name: '标记取消' }));

    expect(await screen.findByText('已取消')).toBeInTheDocument();
    expect(updateInterview).toHaveBeenCalledWith(interview.id, { status: 'CANCELLED' });
    expect(apiClient.updateApplication).not.toHaveBeenCalled();
  });

  it('requires confirmation before deleting a round and removes it from the view', async () => {
    const job = createJob();
    const application = createApplication('interviewing');
    const interview = createInterviewRound();
    const deleteInterview = vi.fn().mockResolvedValue(undefined);
    const apiClient = createApiClient({
      getJob: vi.fn().mockResolvedValue(job),
      listApplications: vi
        .fn()
        .mockResolvedValue(page([{ ...application, jobTitle: job.title, company: job.company }])),
      listInterviews: vi.fn().mockResolvedValue(page([interview])),
      deleteInterview,
    });
    const confirmDelete = vi
      .spyOn(window, 'confirm')
      .mockReturnValueOnce(false)
      .mockReturnValueOnce(true);
    window.history.replaceState(null, '', `/?jobId=${job.id}`);

    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '删除面试' }));
    expect(deleteInterview).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '删除面试' }));

    expect(confirmDelete).toHaveBeenCalledWith('删除该轮面试及其题目记录？');
    await vi.waitFor(() => expect(deleteInterview).toHaveBeenCalledWith(interview.id));
    expect(await screen.findByText('还没有面试记录')).toBeInTheDocument();
  });

  it('adds, edits and deletes an actual interview question with manual performance', async () => {
    const job = createJob();
    const application = createApplication('interviewing');
    let interview = createInterviewRound();
    const createInterviewQuestion = vi.fn(
      async (_interviewId: string, input: CreateInterviewQuestionInput) => {
        const question = createQuestion(input);
        interview = { ...interview, questions: [question] };
        return question;
      },
    );
    const updateInterviewQuestion = vi.fn(
      async (_questionId: string, input: CreateInterviewQuestionInput) => {
        const question = { ...interview.questions[0]!, ...input };
        interview = { ...interview, questions: [question] };
        return question;
      },
    );
    const deleteInterviewQuestion = vi.fn(async () => {
      interview = { ...interview, questions: [] };
    });
    const apiClient = createApiClient({
      getJob: vi.fn().mockResolvedValue(job),
      listApplications: vi
        .fn()
        .mockResolvedValue(page([{ ...application, jobTitle: job.title, company: job.company }])),
      listInterviews: vi.fn().mockResolvedValue(page([interview])),
      createInterviewQuestion,
      updateInterviewQuestion,
      deleteInterviewQuestion,
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    window.history.replaceState(null, '', `/?jobId=${job.id}`);

    render(<App apiClient={apiClient} />);

    fireEvent.click(await screen.findByRole('button', { name: '添加问题' }));
    fireEvent.change(screen.getByLabelText('问题 *'), {
      target: { value: '如何确定产品的北极星指标？' },
    });
    fireEvent.change(screen.getByLabelText('分类'), { target: { value: 'PRODUCT' } });
    fireEvent.change(screen.getByLabelText('我的回答'), {
      target: { value: '先说明用户价值，再拆解可观测行为。' },
    });
    fireEvent.change(screen.getByLabelText('表现'), { target: { value: 'POOR' } });
    fireEvent.change(screen.getByLabelText('题目备注'), {
      target: { value: '没有给出反例。' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存题目' }));

    expect(
      await screen.findByRole('heading', { name: '如何确定产品的北极星指标？' }),
    ).toBeInTheDocument();
    expect(screen.getByText('答得不好')).toBeInTheDocument();
    expect(createInterviewQuestion).toHaveBeenCalledWith(interview.id, {
      question: '如何确定产品的北极星指标？',
      category: 'PRODUCT',
      answerSummary: '先说明用户价值，再拆解可观测行为。',
      performance: 'POOR',
      note: '没有给出反例。',
    });

    fireEvent.click(screen.getByRole('button', { name: '编辑题目' }));
    fireEvent.change(screen.getByLabelText('表现'), { target: { value: 'GOOD' } });
    fireEvent.change(screen.getByLabelText('我的回答'), {
      target: { value: '补充目标、用户价值、行为与反例验证。' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存题目修改' }));

    await vi.waitFor(() =>
      expect(updateInterviewQuestion).toHaveBeenCalledWith(
        'question-1',
        expect.objectContaining({
          performance: 'GOOD',
          answerSummary: '补充目标、用户价值、行为与反例验证。',
        }),
      ),
    );
    const deleteButton = await screen.findByRole('button', { name: '删除题目' });
    expect(screen.getByText('答得较好')).toBeInTheDocument();

    fireEvent.click(deleteButton);
    await vi.waitFor(() => expect(deleteInterviewQuestion).toHaveBeenCalledWith('question-1'));
    expect(await screen.findByText('还没有记录题目')).toBeInTheDocument();
  });

  it('shows a feedback loading state while local facts are being read', async () => {
    const apiClient = createApiClient({
      getFeedbackSummary: vi.fn(() => new Promise<FeedbackSummary>(() => undefined)),
    });
    window.history.replaceState(null, '', '/?view=feedback');

    render(<App apiClient={apiClient} />);

    expect(await screen.findByText('正在读取求职复盘…')).toHaveAttribute('role', 'status');
  });

  it('retries a sanitized feedback load error', async () => {
    const empty = createFeedbackSummary({
      hasData: false,
      totals: {
        savedJobs: 1,
        applications: 0,
        interviewApplications: 0,
        interviews: 0,
        questions: 0,
        offers: 0,
        rejected: 0,
      },
      funnel: [
        { stage: 'SAVED_JOBS', count: 1, conversionRate: null },
        { stage: 'APPLICATIONS', count: 0, conversionRate: 0 },
        { stage: 'INTERVIEW_APPLICATIONS', count: 0, conversionRate: null },
        { stage: 'OFFERS', count: 0, conversionRate: null },
      ],
    });
    const getFeedbackSummary = vi
      .fn()
      .mockRejectedValueOnce(new Error('raw sqlite detail'))
      .mockResolvedValueOnce(empty);
    const apiClient = createApiClient({ getFeedbackSummary });
    window.history.replaceState(null, '', '/?view=feedback');

    render(<App apiClient={apiClient} />);

    expect(await screen.findByRole('alert')).toHaveTextContent('求职复盘暂时无法读取。');
    expect(screen.queryByText('raw sqlite detail')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(
      await screen.findByText('完成投递和面试记录后，这里会形成你的求职复盘。'),
    ).toBeInTheDocument();
    expect(getFeedbackSummary).toHaveBeenCalledTimes(2);
  });

  it('shows an unambiguous feedback empty state without a zero-percent success claim', async () => {
    const summary = createFeedbackSummary({
      hasData: false,
      totals: {
        savedJobs: 1,
        applications: 0,
        interviewApplications: 0,
        interviews: 0,
        questions: 0,
        offers: 0,
        rejected: 0,
      },
      funnel: [
        { stage: 'SAVED_JOBS', count: 1, conversionRate: null },
        { stage: 'APPLICATIONS', count: 0, conversionRate: 0 },
        { stage: 'INTERVIEW_APPLICATIONS', count: 0, conversionRate: null },
        { stage: 'OFFERS', count: 0, conversionRate: null },
      ],
    });
    const apiClient = createApiClient({
      getFeedbackSummary: vi.fn().mockResolvedValue(summary),
    });
    window.history.replaceState(null, '', '/?view=feedback');

    render(<App apiClient={apiClient} />);

    expect(await screen.findByRole('heading', { name: '求职复盘' })).toBeInTheDocument();
    expect(
      await screen.findByText('完成投递和面试记录后，这里会形成你的求职复盘。'),
    ).toBeInTheDocument();
    expect(screen.queryByText(/0%|成功率/)).toBeNull();
  });

  it('renders deterministic factual feedback without AI conclusions or recommendations', async () => {
    const apiClient = createApiClient({
      getFeedbackSummary: vi.fn().mockResolvedValue(createFeedbackSummary()),
    });
    window.history.replaceState(null, '', '/?view=feedback');

    render(<App apiClient={apiClient} />);

    const feedback = await screen.findByRole('region', { name: '求职复盘' });
    expect(await within(feedback).findByRole('article', { name: '已保存岗位' })).toHaveTextContent(
      '5',
    );
    expect(within(feedback).getByRole('article', { name: '已投递岗位' })).toHaveTextContent('4');
    expect(within(feedback).getByRole('article', { name: '面试岗位' })).toHaveTextContent('3');
    expect(within(feedback).getByRole('article', { name: 'Offer' })).toHaveTextContent('1');
    expect(within(feedback).getByText('80%')).toBeInTheDocument();
    expect(within(feedback).getByText('75%')).toBeInTheDocument();
    expect(within(feedback).getByText('33%')).toBeInTheDocument();
    expect(within(feedback).getByText('产品：4')).toBeInTheDocument();
    expect(within(feedback).getByText('一般：2')).toBeInTheDocument();
    expect(
      within(feedback).getByText('产品：4 道记录，其中 3 道为“一般/答得不好”'),
    ).toBeInTheDocument();
    expect(within(feedback).getByText('经验匹配：1')).toBeInTheDocument();
    expect(within(feedback).getByRole('row', { name: '产品版 V1 2 2 1' })).toBeInTheDocument();
    expect(within(feedback).getByRole('row', { name: '手动录入 2 2 0' })).toBeInTheDocument();
    expect(within(feedback).queryByText(/系统判定|AI认为|推荐平台/)).toBeNull();
  });

  it('manages plain-text Resume Versions from the dedicated workspace view', async () => {
    let resumes: ResumeVersion[] = [];
    const createResumeVersion = vi.fn(async (input: { name: string; content: string }) => {
      const resume = createResume({ name: input.name, content: input.content });
      resumes = [resume];
      return resume;
    });
    const updateResumeVersion = vi.fn(async (_id: string, input: { name?: string }) => {
      resumes = [{ ...resumes[0]!, ...input, updatedAt: '2026-09-05T01:00:00Z' }];
      return resumes[0]!;
    });
    const duplicateResumeVersion = vi.fn(async () => {
      const duplicate = createResume({ id: 'resume-2', name: 'AI 产品经理版 V2 定稿 副本' });
      resumes = [duplicate, ...resumes];
      return duplicate;
    });
    const deleteResumeVersion = vi.fn(async (id: string) => {
      resumes = resumes.filter((item) => item.id !== id);
    });
    const apiClient = createApiClient({
      listResumeVersions: vi.fn(async () => page(resumes)),
      createResumeVersion,
      updateResumeVersion,
      duplicateResumeVersion,
      deleteResumeVersion,
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<App apiClient={apiClient} />);

    fireEvent.click(await screen.findByRole('button', { name: '简历版本' }));
    expect(await screen.findByText('还没有简历版本')).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: '新建简历版本' })[0]!);
    fireEvent.change(screen.getByLabelText('版本名称 *'), {
      target: { value: 'AI 产品经理版 V2' },
    });
    fireEvent.change(screen.getByLabelText('简历正文 *'), {
      target: { value: '使用 SQL 完成业务数据统计。' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存简历版本' }));

    expect(await screen.findByRole('heading', { name: 'AI 产品经理版 V2' })).toBeInTheDocument();
    expect(createResumeVersion).toHaveBeenCalledWith({
      name: 'AI 产品经理版 V2',
      content: '使用 SQL 完成业务数据统计。',
    });

    fireEvent.click(screen.getByRole('button', { name: '查看' }));
    expect(screen.queryByLabelText('简历正文 *')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '编辑简历' }));
    fireEvent.change(screen.getByLabelText('版本名称 *'), {
      target: { value: 'AI 产品经理版 V2 定稿' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }));
    expect(
      await screen.findByRole('heading', { name: 'AI 产品经理版 V2 定稿' }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /返回简历版本/ }));
    fireEvent.click(screen.getByRole('button', { name: '复制' }));
    expect(
      await screen.findByRole('heading', { name: 'AI 产品经理版 V2 定稿 副本' }),
    ).toBeInTheDocument();
    expect(duplicateResumeVersion).toHaveBeenCalledWith('resume-1', {
      name: 'AI 产品经理版 V2 定稿 副本',
    });

    fireEvent.click(screen.getAllByRole('button', { name: '删除' })[0]!);
    expect(deleteResumeVersion).toHaveBeenCalledWith('resume-2');
  });

  it('shows a Resume as readable sections and preserves the complete original text for editing', async () => {
    const content = [
      '示例候选人',
      '求职方向：产品经理',
      '教育经历',
      '2022.09 - 至今  示例大学  信息管理  本科',
      '荣誉：校级奖学金',
      '实习经历',
      '2025.03 - 2025.08  示例公司  产品实习生',
      '项目经历',
      'JobPilot：负责需求分析与版本验收',
      '个人技能和证书',
      'SQL、Python、Figma',
    ].join('\n');
    const resume = createResume({ content });
    const updateResumeVersion = vi.fn(
      async (_id: string, input: { name?: string; content?: string }) => ({
        ...resume,
        ...input,
        updatedAt: '2026-09-08T08:00:00Z',
      }),
    );
    const apiClient = createApiClient({
      listResumeVersions: vi.fn().mockResolvedValue(page([resume])),
      updateResumeVersion,
    });
    render(<App apiClient={apiClient} />);

    fireEvent.click(await screen.findByRole('button', { name: '简历版本' }));
    fireEvent.click(await screen.findByRole('button', { name: '查看' }));

    expect(screen.getByRole('region', { name: '基本信息' })).toHaveTextContent('示例候选人');
    expect(screen.getByRole('region', { name: '教育经历' })).toHaveTextContent('示例大学');
    expect(screen.getByRole('region', { name: '教育经历' })).toHaveTextContent('校级奖学金');
    expect(screen.getByRole('region', { name: '工作 / 实习经历' })).toHaveTextContent('产品实习生');
    expect(screen.getByRole('region', { name: '项目经历' })).toHaveTextContent('JobPilot');
    expect(screen.getByRole('region', { name: '技能 / 证书' })).toHaveTextContent(
      'SQL、Python、Figma',
    );
    expect(screen.queryByRole('region', { name: '荣誉 / 奖项' })).toBeNull();
    expect(screen.queryByRole('textbox')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: '编辑简历' }));
    expect(screen.queryByLabelText('简历正文 *')).toBeNull();
    expect(screen.getByLabelText('基本信息')).toHaveValue('示例候选人\n求职方向：产品经理');
    expect(screen.getByLabelText('教育经历')).toHaveValue(
      '2022.09 - 至今  示例大学  信息管理  本科\n荣誉：校级奖学金',
    );
    expect(screen.getByLabelText('工作 / 实习经历')).toHaveValue(
      '2025.03 - 2025.08  示例公司  产品实习生',
    );
    expect(screen.getByLabelText('项目经历')).toHaveValue('JobPilot：负责需求分析与版本验收');
    expect(screen.getByLabelText('技能 / 证书')).toHaveValue('SQL、Python、Figma');

    fireEvent.change(screen.getByLabelText('项目经历'), {
      target: { value: 'JobPilot：负责需求分析、版本验收与用户测试' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }));

    expect(updateResumeVersion).toHaveBeenCalledWith('resume-1', {
      name: resume.name,
      content: content.replace(
        'JobPilot：负责需求分析与版本验收',
        'JobPilot：负责需求分析、版本验收与用户测试',
      ),
    });
  });

  it('opens resume import from the Resume Versions view without parsing or saving early', async () => {
    const apiClient = createApiClient();
    render(<App apiClient={apiClient} />);

    fireEvent.click(await screen.findByRole('button', { name: '简历版本' }));
    fireEvent.click(await screen.findByRole('button', { name: '导入简历' }));

    expect(await screen.findByRole('heading', { name: '导入简历' })).toBeInTheDocument();
    expect(screen.getByText(/先解析预览，确认后才写入/)).toBeInTheDocument();
    expect(apiClient.parseResumeImport).not.toHaveBeenCalled();
    expect(apiClient.confirmResumeImport).not.toHaveBeenCalled();
  });

  it('keeps an in-use Resume Version visible when deletion is blocked', async () => {
    const resume = createResume({ applicationCount: 1 });
    const apiClient = createApiClient({
      listResumeVersions: vi.fn().mockResolvedValue(page([resume])),
      deleteResumeVersion: vi
        .fn()
        .mockRejectedValue(new Error('该简历版本已关联投递记录，无法直接删除。')),
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<App apiClient={apiClient} />);

    fireEvent.click(await screen.findByRole('button', { name: '简历版本' }));
    fireEvent.click(await screen.findByRole('button', { name: '删除' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      '该简历版本已关联投递记录，无法直接删除。',
    );
    expect(screen.getByRole('heading', { name: resume.name })).toBeInTheDocument();
  });

  it('creates and edits the local structured Autofill Profile without importing a Resume', async () => {
    const savedProfile = createAutofillProfile();
    const replaceAutofillProfile = vi.fn(async () => ({ profile: savedProfile }));
    const apiClient = createApiClient({
      getAutofillProfile: vi.fn().mockResolvedValue({ profile: null }),
      replaceAutofillProfile,
    });
    render(<App apiClient={apiClient} />);

    fireEvent.click(await screen.findByRole('button', { name: '求职资料' }));
    expect(await screen.findByRole('heading', { name: '求职资料' })).toBeInTheDocument();
    expect(screen.getByText('资料只保存在本机 SQLite')).toBeInTheDocument();
    expect(screen.getByText(/只有在简历导入预览中明确确认后才会更新所选资料/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /从简历导入/ })).toBeNull();

    fireEvent.change(screen.getByLabelText('姓名'), { target: { value: '示例用户' } });
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '000-0000-0000' } });
    fireEvent.change(screen.getByLabelText('邮箱'), {
      target: { value: 'candidate@example.invalid' },
    });
    fireEvent.change(screen.getByLabelText('当前城市'), { target: { value: '示例市' } });

    fireEvent.click(screen.getByRole('button', { name: '添加教育经历' }));
    fireEvent.change(screen.getByLabelText('学校 1'), { target: { value: '示例大学' } });
    fireEvent.change(screen.getByLabelText('专业 1'), { target: { value: '信息管理' } });
    fireEvent.change(screen.getByLabelText('学历 1'), { target: { value: '本科' } });

    fireEvent.click(screen.getByRole('button', { name: '添加工作或实习经历' }));
    fireEvent.change(screen.getByLabelText('公司 1'), { target: { value: '示例公司' } });
    fireEvent.change(screen.getByLabelText('职位 1'), { target: { value: '产品实习生' } });
    fireEvent.change(screen.getByLabelText('经历描述 1'), {
      target: { value: '梳理需求并跟进验收。' },
    });
    fireEvent.click(screen.getByRole('button', { name: '添加项目经历' }));
    fireEvent.change(screen.getByLabelText('项目名称 1'), { target: { value: 'JobPilot' } });
    fireEvent.change(screen.getByLabelText('项目角色 1'), { target: { value: '产品负责人' } });
    fireEvent.change(screen.getByLabelText('项目描述 1'), {
      target: { value: '完成需求分析与阶段验收。' },
    });
    fireEvent.change(screen.getByLabelText('GitHub'), {
      target: { value: 'https://github.com/example-candidate' },
    });

    fireEvent.click(screen.getByRole('button', { name: '保存求职资料' }));

    await vi.waitFor(() => expect(replaceAutofillProfile).toHaveBeenCalledOnce());
    expect(replaceAutofillProfile).toHaveBeenCalledWith(
      expect.objectContaining({
        personal: {
          name: '示例用户',
          phone: '000-0000-0000',
          email: 'candidate@example.invalid',
          currentCity: '示例市',
        },
        education: [expect.objectContaining({ school: '示例大学', major: '信息管理' })],
        experience: [expect.objectContaining({ company: '示例公司', position: '产品实习生' })],
        projects: [expect.objectContaining({ name: 'JobPilot', role: '产品负责人' })],
      }),
    );
    expect(await screen.findByText('求职资料已保存到本机。')).toBeInTheDocument();
  });

  it('explicitly saves the Resume Version used by an existing Application', async () => {
    const job = createJob();
    const resume = createResume();
    const application = createApplication('planned');
    const updateApplication = vi.fn(
      async (_id: string, input: { resumeVersionId?: string | null }) => ({
        ...application,
        resumeVersionId: input.resumeVersionId ?? null,
      }),
    );
    const apiClient = createApiClient({
      listJobs: vi.fn().mockResolvedValue(page([{ ...job, applicationStatus: 'planned' }])),
      getJob: vi.fn().mockResolvedValue(job),
      listApplications: vi
        .fn()
        .mockResolvedValue(page([{ ...application, jobTitle: job.title, company: job.company }])),
      listResumeVersions: vi.fn().mockResolvedValue(page([resume])),
      updateApplication,
    });
    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看详情' }));

    fireEvent.change(await screen.findByLabelText('本次投递使用简历'), {
      target: { value: resume.id },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存使用版本' }));

    expect(updateApplication).toHaveBeenCalledWith(application.id, {
      resumeVersionId: resume.id,
    });
    expect(await screen.findByText('已记录本次投递使用的简历版本。')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('本次投递使用简历'), {
      target: { value: '' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存使用版本' }));
    await vi.waitFor(() => {
      expect(updateApplication).toHaveBeenLastCalledWith(application.id, {
        resumeVersionId: null,
      });
    });
  });

  it('hides the legacy Evidence Map while keeping Copilot available on Job detail', async () => {
    const job = createJob();
    const resume = createResume();
    const apiClient = createApiClient({
      listJobs: vi.fn().mockResolvedValue(page([{ ...job, applicationStatus: null }])),
      getJob: vi.fn().mockResolvedValue(job),
      listResumeVersions: vi.fn().mockResolvedValue(page([resume])),
      getJobAnalysis: vi.fn().mockResolvedValue(createAnalysisResponse()),
    });
    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看详情' }));

    expect(await screen.findByRole('region', { name: 'AI 求职 Copilot' })).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: '简历综合证据分析' })).toBeNull();
    expect(screen.queryByLabelText('用于证据匹配的简历版本')).toBeNull();
    expect(apiClient.getJobEvidenceMap).not.toHaveBeenCalled();
    expect(apiClient.generateJobEvidenceMap).not.toHaveBeenCalled();
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
    createInterview: vi.fn(),
    listInterviews: vi.fn().mockResolvedValue(page([])),
    getInterview: vi.fn(),
    updateInterview: vi.fn(),
    deleteInterview: vi.fn(),
    createInterviewQuestion: vi.fn(),
    updateInterviewQuestion: vi.fn(),
    deleteInterviewQuestion: vi.fn(),
    getFeedbackSummary: vi.fn(),
    getAutofillProfile: vi.fn(),
    replaceAutofillProfile: vi.fn(),
    getJobAnalysis: vi.fn().mockResolvedValue({ isConfigured: false, analysis: null }),
    analyzeJob: vi.fn(),
    getJobEvidenceMap: vi.fn().mockResolvedValue({ isConfigured: false, evidenceMap: null }),
    generateJobEvidenceMap: vi.fn(),
    getJobMatch: vi.fn().mockResolvedValue({ isConfigured: false, record: null }),
    generateJobMatch: vi.fn(),
    getResumeAdvice: vi.fn().mockResolvedValue({ isConfigured: false, record: null }),
    generateResumeAdvice: vi.fn(),
    getInterviewPrep: vi.fn().mockResolvedValue({ isConfigured: false, record: null }),
    generateInterviewPrep: vi.fn(),
    getCopilotRecord: vi.fn(),
    createResumeVersion: vi.fn(),
    listResumeVersions: vi.fn().mockResolvedValue(page([])),
    getResumeVersion: vi.fn(),
    updateResumeVersion: vi.fn(),
    duplicateResumeVersion: vi.fn(),
    deleteResumeVersion: vi.fn(),
    parseResumeImport: vi.fn(),
    confirmResumeImport: vi.fn(),
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
    resumeVersionId: null,
    outcomeNote: null,
    rejectionReason: null,
    appliedAt: status === 'applied' ? '2026-09-03T00:01:00Z' : null,
    createdAt: '2026-09-03T00:00:00Z',
    updatedAt: '2026-09-03T00:01:00Z',
  };
}

function createResume(overrides: Partial<ResumeVersion> = {}): ResumeVersion {
  return {
    id: 'resume-1',
    name: 'AI 产品经理版 V2',
    content: '使用 SQL 完成业务数据统计。\n参与需求评审和版本验收。',
    applicationCount: 0,
    createdAt: '2026-09-05T00:00:00Z',
    updatedAt: '2026-09-05T00:00:00Z',
    ...overrides,
  };
}

function createAutofillProfile(): AutofillProfile {
  return {
    personal: {
      name: '示例用户',
      phone: '000-0000-0000',
      email: 'candidate@example.invalid',
      currentCity: '示例市',
    },
    education: [
      {
        school: '示例大学',
        major: '信息管理',
        degree: '本科',
        start: null,
        end: null,
      },
    ],
    experience: [
      {
        company: '示例公司',
        position: '产品实习生',
        start: null,
        end: null,
        description: '梳理需求并跟进验收。',
      },
    ],
    projects: [
      {
        name: 'JobPilot',
        role: '产品负责人',
        start: null,
        end: null,
        description: '完成需求分析与阶段验收。',
      },
    ],
    links: {
      github: 'https://github.com/example-candidate',
      portfolio: null,
      homepage: null,
    },
    createdAt: '2026-09-07T00:00:00Z',
    updatedAt: '2026-09-07T00:00:00Z',
  };
}

function createInterviewRound(
  overrides: Partial<InterviewRound> | CreateInterviewRoundInput = {},
): InterviewRound {
  return {
    id: 'interview-1',
    applicationId: 'application-1',
    roundName: '一面',
    interviewType: 'VIDEO',
    scheduledAt: '2026-09-08T06:30:00Z',
    status: 'PLANNED',
    interviewerNote: null,
    wentWell: null,
    couldImprove: null,
    learningNotes: null,
    otherNotes: null,
    questions: [],
    createdAt: '2026-09-06T00:00:00Z',
    updatedAt: '2026-09-06T00:00:00Z',
    ...overrides,
  };
}

function createQuestion(
  overrides: Partial<InterviewQuestion> | CreateInterviewQuestionInput = {},
): InterviewQuestion {
  return {
    id: 'question-1',
    interviewRoundId: 'interview-1',
    question: '如何确定产品的北极星指标？',
    category: 'PRODUCT',
    answerSummary: null,
    performance: 'NOT_SURE',
    note: null,
    createdAt: '2026-09-06T00:00:00Z',
    updatedAt: '2026-09-06T00:00:00Z',
    ...overrides,
  };
}

function createFeedbackSummary(overrides: Partial<FeedbackSummary> = {}): FeedbackSummary {
  return {
    hasData: true,
    totals: {
      savedJobs: 5,
      applications: 4,
      interviewApplications: 3,
      interviews: 4,
      questions: 4,
      offers: 1,
      rejected: 2,
    },
    funnel: [
      { stage: 'SAVED_JOBS', count: 5, conversionRate: null },
      { stage: 'APPLICATIONS', count: 4, conversionRate: 0.8 },
      { stage: 'INTERVIEW_APPLICATIONS', count: 3, conversionRate: 0.75 },
      { stage: 'OFFERS', count: 1, conversionRate: 1 / 3 },
    ],
    questionCategories: [
      { category: 'PRODUCT', count: 4 },
      { category: 'PROJECT', count: 0 },
    ],
    performances: [
      { performance: 'GOOD', count: 1 },
      { performance: 'OK', count: 2 },
      { performance: 'POOR', count: 1 },
      { performance: 'NOT_SURE', count: 0 },
    ],
    weakCategories: [{ category: 'PRODUCT', questionCount: 4, weakCount: 3 }],
    rejectionReasons: [{ reason: 'EXPERIENCE', count: 1 }],
    unrecordedRejectionReasons: 1,
    resumeVersions: [
      {
        resumeVersionId: 'resume-1',
        resumeVersionName: '产品版 V1',
        applications: 2,
        interviewApplications: 2,
        offers: 1,
      },
    ],
    sources: [{ source: 'manual', applications: 2, interviewApplications: 2, offers: 0 }],
    ...overrides,
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
