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
      'JOB_SOURCE_LABELS',
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
    appliedAt: status === 'applied' ? '2026-09-03T00:01:00Z' : null,
    createdAt: '2026-09-03T00:00:00Z',
    updatedAt: '2026-09-03T00:01:00Z',
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
