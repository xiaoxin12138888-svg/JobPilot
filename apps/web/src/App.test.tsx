import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type {
  ApiClient,
  Application,
  CreateJobInput,
  CreateInterviewRoundInput,
  InterviewRound,
  Job,
  JobAnalysisResponse,
  JobEvidenceMapResponse,
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
    expect(screen.getByText('聚焦 AI 产品需求与方案设计。')).toBeInTheDocument();
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

    fireEvent.click(screen.getByRole('button', { name: '查看/编辑' }));
    fireEvent.change(screen.getByLabelText('版本名称 *'), {
      target: { value: 'AI 产品经理版 V2 定稿' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }));
    expect(
      await screen.findByRole('heading', { name: 'AI 产品经理版 V2 定稿' }),
    ).toBeInTheDocument();

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

  it('requires a selected Resume and current JD analysis before Evidence Map generation', async () => {
    const job = createJob();
    const resume = createResume();
    const apiClient = createApiClient({
      listJobs: vi.fn().mockResolvedValue(page([{ ...job, applicationStatus: null }])),
      getJob: vi.fn().mockResolvedValue(job),
      listResumeVersions: vi.fn().mockResolvedValue(page([resume])),
      getJobAnalysis: vi.fn().mockResolvedValue({ isConfigured: true, analysis: null }),
    });
    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看详情' }));

    expect(await screen.findByText('请选择一个简历版本')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('用于证据匹配的简历版本'), {
      target: { value: resume.id },
    });
    expect(await screen.findByText('请先完成岗位 AI 分析。')).toBeInTheDocument();
    expect(apiClient.generateJobEvidenceMap).not.toHaveBeenCalled();
  });

  it('shows an Evidence prerequisite error when the JD analysis state cannot be loaded', async () => {
    const job = createJob();
    const resume = createResume();
    const apiClient = createApiClient({
      listJobs: vi.fn().mockResolvedValue(page([{ ...job, applicationStatus: null }])),
      getJob: vi.fn().mockResolvedValue(job),
      listResumeVersions: vi.fn().mockResolvedValue(page([resume])),
      getJobAnalysis: vi.fn().mockRejectedValue(new Error('untrusted API response')),
    });
    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看详情' }));
    fireEvent.change(await screen.findByLabelText('用于证据匹配的简历版本'), {
      target: { value: resume.id },
    });

    expect(await screen.findByText('岗位分析状态暂时无法读取，请稍后重试。')).toBeInTheDocument();
    expect(apiClient.getJobEvidenceMap).not.toHaveBeenCalled();
  });

  it('keeps local Resume features available when the Evidence provider is not configured', async () => {
    const job = createJob();
    const resume = createResume();
    const apiClient = createApiClient({
      listJobs: vi.fn().mockResolvedValue(page([{ ...job, applicationStatus: null }])),
      getJob: vi.fn().mockResolvedValue(job),
      listResumeVersions: vi.fn().mockResolvedValue(page([resume])),
      getJobAnalysis: vi.fn().mockResolvedValue(createAnalysisResponse()),
      getJobEvidenceMap: vi.fn().mockResolvedValue({ isConfigured: false, evidenceMap: null }),
    });
    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看详情' }));
    fireEvent.change(await screen.findByLabelText('用于证据匹配的简历版本'), {
      target: { value: resume.id },
    });

    expect(await screen.findByText('AI 服务未配置')).toBeInTheDocument();
    expect(screen.getByText(resume.name)).toBeInTheDocument();
    expect(apiClient.generateJobEvidenceMap).not.toHaveBeenCalled();
  });

  it('confirms external AI sending, shows progress, and renders deterministic Evidence totals', async () => {
    const job = createJob();
    const resume = createResume();
    let resolveGeneration: ((value: JobEvidenceMapResponse) => void) | undefined;
    const generation = new Promise<JobEvidenceMapResponse>((resolve) => {
      resolveGeneration = resolve;
    });
    const generated = createEvidenceMapResponse();
    const apiClient = createApiClient({
      listJobs: vi.fn().mockResolvedValue(page([{ ...job, applicationStatus: null }])),
      getJob: vi.fn().mockResolvedValue(job),
      listResumeVersions: vi.fn().mockResolvedValue(page([resume])),
      getJobAnalysis: vi.fn().mockResolvedValue(createAnalysisResponse()),
      getJobEvidenceMap: vi.fn().mockResolvedValue({ isConfigured: true, evidenceMap: null }),
      generateJobEvidenceMap: vi.fn().mockReturnValue(generation),
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看详情' }));
    fireEvent.change(await screen.findByLabelText('用于证据匹配的简历版本'), {
      target: { value: resume.id },
    });
    fireEvent.click(await screen.findByRole('button', { name: '生成证据映射' }));

    expect(screen.getByRole('button', { name: '正在综合分析岗位条件与简历证据…' })).toBeDisabled();
    expect(window.confirm).toHaveBeenCalledWith(
      '本次分析会将当前选择的简历正文与岗位的六类结构化条件发送至你配置的 AI 服务，用于综合证据判断。是否继续？',
    );

    await act(async () => resolveGeneration?.(generated));
    expect(
      await screen.findByText(
        '共分析 6 项：直接证据 2 项，部分支持 / 待确认 2 项，当前无法证明 2 项。',
      ),
    ).toBeInTheDocument();
    const evidenceRegion = screen.getByRole('region', { name: '简历综合证据分析' });
    for (const heading of ['硬性要求', '加分项', '岗位职责', '技能', '经验', '学历']) {
      expect(within(evidenceRegion).getByRole('heading', { name: heading })).toBeInTheDocument();
    }
    expect(within(evidenceRegion).getAllByText('结论：直接证据')).toHaveLength(2);
    expect(within(evidenceRegion).getAllByText('结论：部分支持 / 待确认')).toHaveLength(2);
    expect(within(evidenceRegion).getAllByText('结论：当前无法证明')).toHaveLength(2);
    expect(within(evidenceRegion).getByRole('heading', { name: '待确认事项' })).toBeInTheDocument();
    expect(
      within(evidenceRegion).getByRole('heading', { name: '主要证据缺口' }),
    ).toBeInTheDocument();
    expect(screen.getByText('使用 SQL 完成业务数据统计')).toBeInTheDocument();
    const firstMapping = within(evidenceRegion).getByRole('article', {
      name: '岗位条件：能够分析需求',
    });
    const detailHeadings = within(firstMapping).getAllByRole('heading', { level: 5 });
    expect(detailHeadings.map((heading) => heading.textContent)).toEqual([
      '判断依据',
      '简历原文证据',
    ]);
    expect(screen.queryByText(/%|匹配率|Offer 概率/)).toBeNull();
  });

  it('keeps a stale Evidence Map visible when regeneration fails', async () => {
    const job = createJob();
    const resume = createResume();
    const stale = createEvidenceMapResponse();
    stale.evidenceMap!.isStale = true;
    const apiClient = createApiClient({
      listJobs: vi.fn().mockResolvedValue(page([{ ...job, applicationStatus: null }])),
      getJob: vi.fn().mockResolvedValue(job),
      listResumeVersions: vi.fn().mockResolvedValue(page([resume])),
      getJobAnalysis: vi.fn().mockResolvedValue(createAnalysisResponse()),
      getJobEvidenceMap: vi.fn().mockResolvedValue(stale),
      generateJobEvidenceMap: vi.fn().mockRejectedValue(new Error('raw resume and provider error')),
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '查看详情' }));
    fireEvent.change(await screen.findByLabelText('用于证据匹配的简历版本'), {
      target: { value: resume.id },
    });

    expect(
      await screen.findByText('岗位或简历内容已更新，请重新生成证据映射。'),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重新生成证据映射' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'AI证据匹配暂时不可用，请稍后重试。',
    );
    expect(screen.getByText('使用 SQL 完成业务数据统计')).toBeInTheDocument();
    expect(screen.queryByText('raw resume and provider error')).toBeNull();
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
    getJobAnalysis: vi.fn().mockResolvedValue({ isConfigured: false, analysis: null }),
    analyzeJob: vi.fn(),
    getJobEvidenceMap: vi.fn().mockResolvedValue({ isConfigured: false, evidenceMap: null }),
    generateJobEvidenceMap: vi.fn(),
    createResumeVersion: vi.fn(),
    listResumeVersions: vi.fn().mockResolvedValue(page([])),
    getResumeVersion: vi.fn(),
    updateResumeVersion: vi.fn(),
    duplicateResumeVersion: vi.fn(),
    deleteResumeVersion: vi.fn(),
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

function createEvidenceMapResponse(): JobEvidenceMapResponse {
  return {
    isConfigured: true,
    evidenceMap: {
      id: 'map-1',
      jobId: 'job-1',
      resumeVersionId: 'resume-1',
      schemaVersion: 2,
      result: {
        mappings: [
          {
            requirementType: 'MUST_HAVE',
            requirementText: '能够分析需求',
            coverage: 'DIRECT',
            resumeEvidence: [{ quote: '使用 SQL 完成业务数据统计' }],
            reason: '简历原文提供了直接证据。',
          },
          {
            requirementType: 'PREFERRED',
            requirementText: '完整上线经验',
            coverage: 'PARTIAL',
            resumeEvidence: [{ quote: '参与需求评审和版本验收' }],
            reason: '有相关环节经验，但未完整证明。',
          },
          {
            requirementType: 'RESPONSIBILITY',
            requirementText: '负责市场调研',
            coverage: 'DIRECT',
            resumeEvidence: [{ quote: '完成用户与竞品调研' }],
            reason: '简历原文直接说明了调研职责。',
          },
          {
            requirementType: 'SKILL',
            requirementText: 'Python',
            coverage: 'PARTIAL',
            resumeEvidence: [{ quote: '使用 Python 清洗业务数据' }],
            reason: '存在实际使用记录，但未证明岗位要求的熟练程度。',
          },
          {
            requirementType: 'EXPERIENCE',
            requirementText: '三年产品经验',
            coverage: 'GAP',
            resumeEvidence: [],
            reason: '当前简历版本中未发现可证明年限的内容。',
          },
          {
            requirementType: 'EDUCATION',
            requirementText: '本科及以上',
            coverage: 'GAP',
            resumeEvidence: [],
            reason: '当前简历版本中未发现明确学历内容。',
          },
        ],
      },
      isStale: false,
      createdAt: '2026-09-05T00:00:00Z',
      updatedAt: '2026-09-05T00:00:00Z',
    },
  };
}
