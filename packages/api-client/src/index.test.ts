import { afterEach, describe, expect, it, vi } from 'vitest';

import * as apiClientModule from './index';
import { ApiRequestError, createApiClient } from './index';

const healthyPayload = {
  status: 'ok',
  service: 'jobpilot-api',
} as const;

afterEach(() => {
  vi.useRealTimers();
});

describe('createApiClient', () => {
  it('exports only the intended client runtime surface', () => {
    expect(Object.keys(apiClientModule).sort()).toEqual([
      'APPLICATION_STATUS_LABELS',
      'ApiRequestError',
      'INTERVIEW_STATUS_LABELS',
      'INTERVIEW_TYPE_LABELS',
      'JOB_SOURCE_LABELS',
      'QUESTION_CATEGORY_LABELS',
      'QUESTION_PERFORMANCE_LABELS',
      'REJECTION_REASON_LABELS',
      'createApiClient',
      'validateApiBaseUrl',
    ]);
  });

  it('gets and validates the exact API health response without credentials or redirects', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(healthyPayload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const client = createApiClient({
      baseUrl: 'http://127.0.0.1:8000/base-path',
      fetchImplementation,
    });

    await expect(client.getHealth()).resolves.toEqual(healthyPayload);
    expect(fetchImplementation).toHaveBeenCalledOnce();
    expect(fetchImplementation).toHaveBeenCalledWith('http://127.0.0.1:8000/health', {
      cache: 'no-store',
      credentials: 'omit',
      headers: { Accept: 'application/json' },
      method: 'GET',
      redirect: 'error',
      signal: expect.any(AbortSignal),
    });
  });

  it.each(['http://localhost:8000', 'http://127.0.0.1:8000', 'http://[::1]:8000'])(
    'accepts the loopback API base URL %s',
    (baseUrl) => {
      expect(() =>
        createApiClient({ baseUrl, fetchImplementation: vi.fn<typeof fetch>() }),
      ).not.toThrow();
    },
  );

  it.each([
    'https://api.jobpilot.example.com',
    'http://192.168.1.10:8000',
    'http://0.0.0.0:8000',
    'http://[::]:8000',
  ])('rejects the non-loopback API base URL %s', (baseUrl) => {
    expect(() => createApiClient({ baseUrl, fetchImplementation: vi.fn<typeof fetch>() })).toThrow(
      'API base URL must use a loopback host',
    );
  });

  it('rejects a non-HTTP API base URL', () => {
    expect(() => createApiClient({ baseUrl: 'file:///tmp/jobpilot' })).toThrow(
      'API base URL must use HTTP or HTTPS',
    );
  });

  it('rejects credentials in the API base URL', () => {
    expect(() => createApiClient({ baseUrl: 'http://user:secret@127.0.0.1:8000' })).toThrow(
      'API base URL must not include credentials',
    );
  });

  it.each([201, 204, 503])('rejects the non-200 health response %s', async (status) => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(null, { status }));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.getHealth()).rejects.toThrow(`health request failed with status ${status}`);
  });

  it.each([
    ['wrong status', { status: 'starting', service: 'jobpilot-api' }],
    ['wrong service', { status: 'ok', service: 'remote-api' }],
    ['missing field', { status: 'ok' }],
    ['extra field', { ...healthyPayload, deployment: 'remote' }],
    ['array', [healthyPayload]],
  ])('rejects an untrusted %s health payload', async (_caseName, payload) => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.getHealth()).rejects.toThrow('invalid health response');
  });

  it('rejects invalid health JSON', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response('{', { status: 200 }));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.getHealth()).rejects.toThrow('invalid health response');
  });

  it('aborts a health request that remains pending for five seconds', async () => {
    vi.useFakeTimers();
    const fetchImplementation = vi.fn<typeof fetch>((_input, init) => {
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener(
          'abort',
          () => reject(new DOMException('The operation was aborted', 'AbortError')),
          { once: true },
        );
      });
    });
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    const healthRequest = client.getHealth();
    expect(fetchImplementation.mock.calls[0]?.[1]?.signal).toBeInstanceOf(AbortSignal);
    const timeoutExpectation = expect(healthRequest).rejects.toThrow(
      'JobPilot API health request timed out',
    );
    await vi.advanceTimersByTimeAsync(5_000);
    await timeoutExpectation;
  });

  it('creates a manual job with camelCase JSON and no credentials', async () => {
    const job = createJobPayload();
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(job, 201));
    const client = createApiClient({
      baseUrl: 'http://127.0.0.1:8000',
      fetchImplementation,
    });

    await expect(
      client.createJob({
        title: 'AI 产品经理实习生',
        company: '测试公司',
        source: 'manual',
        salaryText: '200-300/天',
      }),
    ).resolves.toEqual(job);
    expect(fetchImplementation).toHaveBeenCalledWith('http://127.0.0.1:8000/api/v1/jobs', {
      body: JSON.stringify({
        title: 'AI 产品经理实习生',
        company: '测试公司',
        source: 'manual',
        salaryText: '200-300/天',
      }),
      cache: 'no-store',
      credentials: 'omit',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      method: 'POST',
      redirect: 'error',
      signal: expect.any(AbortSignal),
    });
  });

  it('accepts and validates a BOSS job response', async () => {
    const job = createJobPayload('boss');
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(job, 201));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(
      client.createJob({
        title: '产品经理',
        company: '测试公司',
        source: 'boss',
        sourceUrl: 'https://www.zhipin.com/job_detail/fixture123.html',
      }),
    ).resolves.toEqual(job);
  });

  it('accepts and validates a Nowcoder job response', async () => {
    const job = createJobPayload('nowcoder');
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(job, 201));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(
      client.createJob({
        title: '产品经理',
        company: '测试公司',
        source: 'nowcoder',
        sourceUrl: 'https://www.nowcoder.com/jobs/detail/448241',
      }),
    ).resolves.toEqual(job);
  });

  it('lists jobs with bounded filters and validates the response', async () => {
    const payload = {
      items: [{ ...createJobPayload(), applicationStatus: 'planned' }],
      total: 1,
      limit: 20,
      offset: 0,
    };
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(
      client.listJobs({ keyword: 'AI', source: 'manual', applicationStatus: 'planned', limit: 20 }),
    ).resolves.toEqual(payload);
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      'http://127.0.0.1:8000/api/v1/jobs?keyword=AI&source=manual&applicationStatus=planned&limit=20',
    );
  });

  it('rejects an untrusted business payload', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ ...createJobPayload(), source: 'unknown' }, 201));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.createJob({ title: '岗位', company: '公司' })).rejects.toThrow(
      'invalid Job response',
    );
  });

  it('surfaces the public API error without leaking a transport detail', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: 'DUPLICATE_JOB_URL',
            message: '该岗位链接已经保存',
            requestId: 'req_1',
            resourceId: 'job-existing',
          },
        },
        409,
      ),
    );
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    const request = client.createJob({ title: '岗位', company: '公司' });
    await expect(request).rejects.toBeInstanceOf(ApiRequestError);
    await expect(request).rejects.toMatchObject({
      name: 'ApiRequestError',
      status: 409,
      code: 'DUPLICATE_JOB_URL',
      message: '该岗位链接已经保存',
      requestId: 'req_1',
      resourceId: 'job-existing',
    });
  });

  it('parses a local resume with multipart transport and no credentials or manual content type', async () => {
    const preview = createResumeImportPreviewPayload();
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(preview));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });
    const file = new File(['local-content'], 'resume.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    });

    await expect(client.parseResumeImport(file)).resolves.toEqual(preview);

    const [url, init] = fetchImplementation.mock.calls[0]!;
    expect(url).toBe('http://127.0.0.1:8000/api/v1/resume-imports/parse');
    expect(init).toMatchObject({
      cache: 'no-store',
      credentials: 'omit',
      headers: { Accept: 'application/json' },
      method: 'POST',
      redirect: 'error',
    });
    expect(init?.body).toBeInstanceOf(FormData);
    const uploaded = (init?.body as FormData).get('file') as File;
    expect(uploaded.name).toBe('resume.docx');
    expect(await uploaded.text()).toBe('local-content');
  });

  it('confirms only the explicitly selected resume and profile values as JSON', async () => {
    const confirmation = {
      resumeVersion: createResumePayload(),
      profile: createAutofillProfilePayload(),
    };
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(confirmation));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });
    const input = {
      resumeVersion: { name: '导入简历 2026-09-07', content: '已编辑正文' },
      profileImport: { personal: { phone: '13800138000' } },
    };

    await expect(client.confirmResumeImport(input)).resolves.toEqual(confirmation);
    expect(fetchImplementation).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/resume-imports/confirm',
      expect.objectContaining({
        body: JSON.stringify(input),
        credentials: 'omit',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        method: 'POST',
        redirect: 'error',
      }),
    );
  });

  it('rejects an untrusted resume import preview shape', async () => {
    const invalid = { ...createResumeImportPreviewPayload(), sourceFilename: 'private.docx' };
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(invalid));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });
    const file = new File(['content'], 'resume.docx');

    await expect(client.parseResumeImport(file)).rejects.toThrow('invalid Resume Import preview');
  });

  it('requires explicit applied confirmation in the status request body', async () => {
    const application = createApplicationPayload('applied');
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(application));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await client.updateApplication('application-1', {
      status: 'applied',
      confirmApplied: true,
    });

    expect(fetchImplementation.mock.calls[0]?.[1]).toMatchObject({
      method: 'PATCH',
      body: JSON.stringify({ status: 'applied', confirmApplied: true }),
      credentials: 'omit',
    });
  });

  it('sets and clears the explicitly selected Application Resume Version', async () => {
    const application = { ...createApplicationPayload('planned'), resumeVersionId: 'resume-1' };
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(application));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(
      client.updateApplication('application-1', { resumeVersionId: 'resume-1' }),
    ).resolves.toEqual(application);
    expect(fetchImplementation.mock.calls[0]?.[1]).toMatchObject({
      method: 'PATCH',
      body: JSON.stringify({ resumeVersionId: 'resume-1' }),
      credentials: 'omit',
    });
  });

  it('records Application outcome detail with no credentials', async () => {
    const application = {
      ...createApplicationPayload('planned'),
      status: 'rejected' as const,
      outcomeNote: '二面后未通过',
      rejectionReason: 'EXPERIENCE' as const,
    };
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(application));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(
      client.updateApplication('application-1', {
        status: 'rejected',
        outcomeNote: '二面后未通过',
        rejectionReason: 'EXPERIENCE',
      }),
    ).resolves.toEqual(application);
    expect(fetchImplementation.mock.calls[0]?.[1]).toMatchObject({
      method: 'PATCH',
      body: JSON.stringify({
        status: 'rejected',
        outcomeNote: '二面后未通过',
        rejectionReason: 'EXPERIENCE',
      }),
      credentials: 'omit',
    });
  });

  it('creates, lists, updates and deletes local interview records', async () => {
    const interview = createInterviewPayload();
    const question = createQuestionPayload();
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(interview, 201))
      .mockResolvedValueOnce(jsonResponse({ items: [interview], total: 1, limit: 20, offset: 0 }))
      .mockResolvedValueOnce(jsonResponse({ ...interview, status: 'COMPLETED' }))
      .mockResolvedValueOnce(jsonResponse(question, 201))
      .mockResolvedValueOnce(jsonResponse({ ...question, performance: 'GOOD' }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(
      client.createInterview('application-1', {
        roundName: '一面',
        interviewType: 'VIDEO',
      }),
    ).resolves.toEqual(interview);
    await expect(
      client.listInterviews('application-1', { limit: 20, offset: 0 }),
    ).resolves.toMatchObject({ total: 1 });
    await expect(
      client.updateInterview('interview-1', { status: 'COMPLETED' }),
    ).resolves.toMatchObject({ status: 'COMPLETED' });
    await expect(
      client.createInterviewQuestion('interview-1', {
        question: '为什么选择这个岗位？',
        category: 'PRODUCT',
        performance: 'OK',
      }),
    ).resolves.toEqual(question);
    await expect(
      client.updateInterviewQuestion('question-1', { performance: 'GOOD' }),
    ).resolves.toMatchObject({ performance: 'GOOD' });
    await expect(client.deleteInterviewQuestion('question-1')).resolves.toBeUndefined();
    await expect(client.deleteInterview('interview-1')).resolves.toBeUndefined();

    expect(fetchImplementation.mock.calls.map((call) => [call[0], call[1]?.method])).toEqual([
      ['http://127.0.0.1:8000/api/v1/applications/application-1/interviews', 'POST'],
      [
        'http://127.0.0.1:8000/api/v1/applications/application-1/interviews?limit=20&offset=0',
        'GET',
      ],
      ['http://127.0.0.1:8000/api/v1/interviews/interview-1', 'PATCH'],
      ['http://127.0.0.1:8000/api/v1/interviews/interview-1/questions', 'POST'],
      ['http://127.0.0.1:8000/api/v1/interview-questions/question-1', 'PATCH'],
      ['http://127.0.0.1:8000/api/v1/interview-questions/question-1', 'DELETE'],
      ['http://127.0.0.1:8000/api/v1/interviews/interview-1', 'DELETE'],
    ]);
    expect(fetchImplementation.mock.calls.every((call) => call[1]?.credentials === 'omit')).toBe(
      true,
    );
  });

  it.each([
    { ...createInterviewPayload(), privateField: 'must-not-pass' },
    { ...createInterviewPayload(), interviewType: 'CHAT' },
    { ...createInterviewPayload(), questions: [{ ...createQuestionPayload(), performance: 80 }] },
  ])('rejects an untrusted Interview payload', async (payload) => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.getInterview('interview-1')).rejects.toThrow('invalid Interview response');
  });

  it('gets and validates the deterministic Feedback Summary', async () => {
    const payload = createFeedbackSummaryPayload();
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.getFeedbackSummary()).resolves.toEqual(payload);
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      'http://127.0.0.1:8000/api/v1/feedback-summary',
    );
    expect(fetchImplementation.mock.calls[0]?.[1]).toMatchObject({
      method: 'GET',
      credentials: 'omit',
    });
  });

  it('gets and replaces the singleton local Autofill Profile without credentials', async () => {
    const profile = createAutofillProfilePayload();
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ profile: null }))
      .mockResolvedValueOnce(jsonResponse({ profile }));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.getAutofillProfile()).resolves.toEqual({ profile: null });
    await expect(
      client.replaceAutofillProfile({
        personal: profile.personal,
        education: profile.education,
        experience: profile.experience,
        links: profile.links,
      }),
    ).resolves.toEqual({ profile });

    expect(fetchImplementation.mock.calls.map((call) => [call[0], call[1]?.method])).toEqual([
      ['http://127.0.0.1:8000/api/v1/autofill-profile', 'GET'],
      ['http://127.0.0.1:8000/api/v1/autofill-profile', 'PUT'],
    ]);
    expect(fetchImplementation.mock.calls[1]?.[1]).toMatchObject({
      credentials: 'omit',
      redirect: 'error',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({
        personal: profile.personal,
        education: profile.education,
        experience: profile.experience,
        links: profile.links,
      }),
    });
  });

  it.each([
    { profile: { ...createAutofillProfilePayload(), privateField: 'must-not-pass' } },
    {
      profile: {
        ...createAutofillProfilePayload(),
        education: [{ ...createAutofillProfilePayload().education[0], start: '2026' }],
      },
    },
    { profile: { ...createAutofillProfilePayload(), links: { homepage: 42 } } },
  ])('rejects an untrusted Autofill Profile payload', async (payload) => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.getAutofillProfile()).rejects.toThrow('invalid Autofill Profile response');
  });

  it.each([
    { ...createFeedbackSummaryPayload(), recommendation: '优先使用 V1' },
    {
      ...createFeedbackSummaryPayload(),
      funnel: [{ stage: 'OFFERS', count: 1, conversionRate: '33%' }],
    },
    {
      ...createFeedbackSummaryPayload(),
      questionCategories: [{ category: 'AUTO', count: 1 }],
    },
  ])('rejects an untrusted Feedback Summary payload', async (payload) => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.getFeedbackSummary()).rejects.toThrow('invalid Feedback Summary response');
  });

  it('loads only the application belonging to one job', async () => {
    const payload = {
      items: [
        {
          ...createApplicationPayload('planned'),
          jobTitle: 'AI 产品经理实习生',
          company: '测试公司',
        },
      ],
      total: 1,
      limit: 1,
      offset: 0,
    };
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await client.listApplications({ jobId: 'job-1', limit: 1 });

    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      'http://127.0.0.1:8000/api/v1/applications?jobId=job-1&limit=1',
    );
  });

  it('gets and validates a nullable Job analysis resource', async () => {
    const payload = { isConfigured: true, analysis: null };
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.getJobAnalysis('job-1')).resolves.toEqual(payload);
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      'http://127.0.0.1:8000/api/v1/jobs/job-1/analysis',
    );
    expect(fetchImplementation.mock.calls[0]?.[1]).toMatchObject({
      method: 'GET',
      credentials: 'omit',
    });
  });

  it('requests analysis with strict empty JSON and accepts the structured result', async () => {
    const payload = createAnalysisPayload();
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.analyzeJob('job-1')).resolves.toEqual(payload);
    expect(fetchImplementation.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      body: '{}',
      credentials: 'omit',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    });
  });

  it.each([
    { ...createAnalysisPayload(), extra: true },
    { isConfigured: true, analysis: { ...createAnalysisPayload().analysis, schemaVersion: 2 } },
    {
      isConfigured: true,
      analysis: {
        ...createAnalysisPayload().analysis,
        result: { ...createAnalysisPayload().analysis.result, skills: 'SQL' },
      },
    },
    {
      isConfigured: true,
      analysis: {
        ...createAnalysisPayload().analysis,
        result: {
          ...createAnalysisPayload().analysis.result,
          responsibilities: [{ text: '职责', evidence: 123 }],
        },
      },
    },
  ])('rejects an untrusted Job analysis payload', async (payload) => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.getJobAnalysis('job-1')).rejects.toThrow('invalid Job analysis response');
  });

  it('creates, lists, updates, duplicates and deletes a Resume Version', async () => {
    const resume = createResumePayload();
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(resume, 201))
      .mockResolvedValueOnce(jsonResponse({ items: [resume], total: 1, limit: 50, offset: 0 }))
      .mockResolvedValueOnce(jsonResponse({ ...resume, name: 'AI 产品经理版 V2' }))
      .mockResolvedValueOnce(
        jsonResponse({ ...resume, id: 'resume-2', name: 'AI 产品经理版 V2' }, 201),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(
      client.createResumeVersion({ name: resume.name, content: resume.content }),
    ).resolves.toEqual(resume);
    await expect(client.listResumeVersions()).resolves.toMatchObject({ total: 1 });
    await expect(
      client.updateResumeVersion(resume.id, { name: 'AI 产品经理版 V2' }),
    ).resolves.toMatchObject({ name: 'AI 产品经理版 V2' });
    await expect(
      client.duplicateResumeVersion(resume.id, { name: 'AI 产品经理版 V2' }),
    ).resolves.toMatchObject({ id: 'resume-2' });
    await expect(client.deleteResumeVersion('resume-2')).resolves.toBeUndefined();

    expect(fetchImplementation.mock.calls.map((call) => [call[0], call[1]?.method])).toEqual([
      ['http://127.0.0.1:8000/api/v1/resume-versions', 'POST'],
      ['http://127.0.0.1:8000/api/v1/resume-versions', 'GET'],
      ['http://127.0.0.1:8000/api/v1/resume-versions/resume-1', 'PATCH'],
      ['http://127.0.0.1:8000/api/v1/resume-versions/resume-1/duplicate', 'POST'],
      ['http://127.0.0.1:8000/api/v1/resume-versions/resume-2', 'DELETE'],
    ]);
  });

  it.each([
    { ...createResumePayload(), applicationCount: -1 },
    { ...createResumePayload(), content: 42 },
    { ...createResumePayload(), privateField: 'must-not-pass' },
  ])('rejects an untrusted Resume Version payload', async (payload) => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.getResumeVersion('resume-1')).rejects.toThrow(
      'invalid Resume Version response',
    );
  });

  it('gets and generates a grounded Evidence Map with explicit external-AI consent', async () => {
    const payload = createEvidenceMapPayload();
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ isConfigured: true, evidenceMap: null }))
      .mockResolvedValueOnce(jsonResponse(payload));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.getJobEvidenceMap('job-1', 'resume-1')).resolves.toEqual({
      isConfigured: true,
      evidenceMap: null,
    });
    await expect(client.generateJobEvidenceMap('job-1', 'resume-1')).resolves.toEqual(payload);

    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      'http://127.0.0.1:8000/api/v1/jobs/job-1/evidence-map?resumeVersionId=resume-1',
    );
    expect(fetchImplementation.mock.calls[1]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ resumeVersionId: 'resume-1', confirmExternalAi: true }),
      credentials: 'omit',
      redirect: 'error',
    });
  });

  it('keeps a legacy schema 1 Evidence Map readable', async () => {
    const payload = createEvidenceMapPayload(1, 'MUST_HAVE');
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.getJobEvidenceMap('job-1', 'resume-1')).resolves.toEqual(payload);
  });

  it.each([
    { ...createEvidenceMapPayload(), score: 98 },
    {
      isConfigured: true,
      evidenceMap: {
        ...createEvidenceMapPayload().evidenceMap,
        result: {
          mappings: [
            {
              ...createEvidenceMapPayload().evidenceMap.result.mappings[0],
              coverage: 'HIGH',
            },
          ],
        },
      },
    },
    {
      isConfigured: true,
      evidenceMap: {
        ...createEvidenceMapPayload().evidenceMap,
        result: {
          mappings: [
            {
              ...createEvidenceMapPayload().evidenceMap.result.mappings[0],
              resumeEvidence: [{ quote: 42 }],
            },
          ],
        },
      },
    },
    {
      isConfigured: true,
      evidenceMap: {
        ...createEvidenceMapPayload(1, 'MUST_HAVE').evidenceMap,
        result: createEvidenceMapPayload(2, 'RESPONSIBILITY').evidenceMap.result,
      },
    },
    {
      isConfigured: true,
      evidenceMap: {
        ...createEvidenceMapPayload().evidenceMap,
        schemaVersion: 3,
      },
    },
    {
      isConfigured: true,
      evidenceMap: {
        ...createEvidenceMapPayload().evidenceMap,
        result: {
          mappings: [
            {
              ...createEvidenceMapPayload().evidenceMap.result.mappings[0],
              requirementType: 'UNKNOWN',
            },
          ],
        },
      },
    },
  ])('rejects an untrusted Evidence Map payload', async (payload) => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(payload));
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    await expect(client.getJobEvidenceMap('job-1', 'resume-1')).rejects.toThrow(
      'invalid Evidence Map response',
    );
  });

  it('allows an Evidence Map request its dedicated 65 second client window', async () => {
    vi.useFakeTimers();
    const fetchImplementation = vi.fn<typeof fetch>((_input, init) => {
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener(
          'abort',
          () => reject(new DOMException('The operation was aborted', 'AbortError')),
          { once: true },
        );
      });
    });
    const client = createApiClient({ baseUrl: 'http://127.0.0.1:8000', fetchImplementation });

    const request = client.generateJobEvidenceMap('job-1', 'resume-1');
    const timeoutExpectation = expect(request).rejects.toThrow('JobPilot API request timed out');
    await vi.advanceTimersByTimeAsync(64_999);
    expect(fetchImplementation.mock.calls[0]?.[1]?.signal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    await timeoutExpectation;
  });
});

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function createJobPayload(source: 'manual' | 'boss' | 'nowcoder' = 'manual') {
  return {
    id: 'job-1',
    title: 'AI 产品经理实习生',
    company: '测试公司',
    location: null,
    salaryText: '200-300/天',
    source,
    sourceUrl: null,
    description: null,
    notes: null,
    createdAt: '2026-09-03T00:00:00Z',
    updatedAt: '2026-09-03T00:00:00Z',
  };
}

function createApplicationPayload(status: 'planned' | 'applied') {
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

function createQuestionPayload() {
  return {
    id: 'question-1',
    interviewRoundId: 'interview-1',
    question: '为什么选择这个岗位？',
    category: 'PRODUCT' as const,
    answerSummary: '结合虚构项目说明动机。',
    performance: 'OK' as const,
    note: null,
    createdAt: '2026-09-06T00:00:00Z',
    updatedAt: '2026-09-06T00:00:00Z',
  };
}

function createInterviewPayload() {
  return {
    id: 'interview-1',
    applicationId: 'application-1',
    roundName: '一面',
    interviewType: 'VIDEO' as const,
    scheduledAt: null,
    status: 'PLANNED' as const,
    interviewerNote: null,
    wentWell: null,
    couldImprove: null,
    learningNotes: null,
    otherNotes: null,
    questions: [] as ReturnType<typeof createQuestionPayload>[],
    createdAt: '2026-09-06T00:00:00Z',
    updatedAt: '2026-09-06T00:00:00Z',
  };
}

function createFeedbackSummaryPayload() {
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
      { stage: 'SAVED_JOBS' as const, count: 5, conversionRate: null },
      { stage: 'APPLICATIONS' as const, count: 4, conversionRate: 0.8 },
      { stage: 'INTERVIEW_APPLICATIONS' as const, count: 3, conversionRate: 0.75 },
      { stage: 'OFFERS' as const, count: 1, conversionRate: 1 / 3 },
    ],
    questionCategories: [{ category: 'PRODUCT' as const, count: 4 }],
    performances: [{ performance: 'OK' as const, count: 4 }],
    weakCategories: [{ category: 'PRODUCT' as const, questionCount: 4, weakCount: 3 }],
    rejectionReasons: [{ reason: 'EXPERIENCE' as const, count: 1 }],
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
    sources: [{ source: 'manual' as const, applications: 2, interviewApplications: 2, offers: 0 }],
  };
}

function createResumePayload() {
  return {
    id: 'resume-1',
    name: 'AI 产品经理版',
    content: '使用 SQL 完成业务数据统计。',
    applicationCount: 0,
    createdAt: '2026-09-05T00:00:00Z',
    updatedAt: '2026-09-05T00:00:00Z',
  };
}

function createAutofillProfilePayload() {
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
        start: '2022-09',
        end: '2026-06',
      },
    ],
    experience: [
      {
        company: '示例公司',
        position: '产品实习生',
        start: '2025-01',
        end: '2025-06',
        description: '梳理需求并跟进验收。',
      },
    ],
    links: {
      github: 'https://github.com/example-candidate',
      portfolio: null,
      homepage: 'https://example.invalid',
    },
    createdAt: '2026-09-07T00:00:00Z',
    updatedAt: '2026-09-07T00:00:00Z',
  };
}

function createResumeImportPreviewPayload() {
  return {
    fileType: 'DOCX' as const,
    extractedText: '基本信息\n示例用户',
    blocks: [
      { kind: 'HEADING' as const, text: '基本信息' },
      { kind: 'TEXT' as const, text: '示例用户' },
    ],
    sections: [{ type: 'BASIC' as const, heading: '基本信息', text: '示例用户' }],
    profileCandidates: {
      personal: {
        name: '示例用户',
        phone: '13800138000',
        email: 'candidate@example.invalid',
        currentCity: null,
      },
      education: [
        {
          school: '示例大学',
          major: '信息管理',
          degree: null,
          start: '2022-09',
          end: null,
        },
      ],
      experience: [],
      links: { github: null, portfolio: null, homepage: null },
    },
    warnings: [{ code: 'EXPERIENCE_NOT_DETECTED', message: '未识别到明确的工作或实习经历' }],
    metrics: {
      fileSizeBytes: 1024,
      pageCount: null,
      parseLatencyMs: 8,
      extractedCharacterCount: 9,
    },
  };
}

function createEvidenceMapPayload(
  schemaVersion: 1 | 2 = 2,
  requirementType:
    | 'MUST_HAVE'
    | 'PREFERRED'
    | 'RESPONSIBILITY'
    | 'SKILL'
    | 'EXPERIENCE'
    | 'EDUCATION' = 'RESPONSIBILITY',
) {
  return {
    isConfigured: true,
    evidenceMap: {
      id: 'map-1',
      jobId: 'job-1',
      resumeVersionId: 'resume-1',
      schemaVersion,
      result: {
        mappings: [
          {
            requirementType,
            requirementText: '负责市场调研与产品分析',
            coverage: 'DIRECT',
            resumeEvidence: [{ quote: '使用 SQL 完成业务数据统计' }],
            reason: '简历原文直接说明 SQL 实践。',
          },
        ],
      },
      isStale: false,
      createdAt: '2026-09-05T00:00:00Z',
      updatedAt: '2026-09-05T00:00:00Z',
    },
  };
}

function createAnalysisPayload() {
  return {
    isConfigured: true,
    analysis: {
      id: 'analysis-1',
      jobId: 'job-1',
      schemaVersion: 1,
      result: {
        summary: '岗位摘要',
        responsibilities: [{ text: '负责需求分析', evidence: '需求分析' }],
        mustHaveRequirements: [],
        preferredRequirements: [],
        skills: ['需求分析'],
        experienceRequirements: [],
        educationRequirements: [],
        domainKeywords: ['AI 产品'],
        interviewFocus: [],
      },
      isStale: false,
      createdAt: '2026-09-04T00:00:00Z',
      updatedAt: '2026-09-04T00:00:00Z',
    },
  };
}
