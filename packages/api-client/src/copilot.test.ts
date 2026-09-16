import { describe, expect, it, vi } from 'vitest';

import { createApiClient } from './index';

const matchResponse = {
  isConfigured: true,
  record: {
    id: 'copilot-1',
    jobId: 'job-1',
    resumeVersionId: 'resume-1',
    kind: 'MATCH',
    schemaVersion: 1,
    result: {
      summary: '经历与岗位有相关证据。',
      strengths: [
        {
          text: '已有需求分析经历。',
          sourceEvidence: {
            text: '参与需求分析',
            sourceType: 'RESUME',
            sourceId: 'resume-1',
          },
        },
      ],
      gaps: [
        {
          text: '当前简历未发现 SQL 证据。',
          sourceEvidence: { text: '熟练使用 SQL', sourceType: 'JOB', sourceId: 'job-1' },
        },
      ],
      suggestions: ['准备一个数据分析案例。'],
    },
    inputFingerprint: 'a'.repeat(64),
    model: 'fictional-model',
    promptVersion: 'match-v1',
    isStale: false,
    createdAt: '2026-09-09T00:00:00Z',
  },
};

describe('Copilot API client', () => {
  it('keeps the Copilot request open for two bounded 60-second provider attempts', async () => {
    vi.useFakeTimers();
    try {
      const fetchImplementation = vi.fn<typeof fetch>(
        (_input, init) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener(
              'abort',
              () => reject(new DOMException('The operation was aborted', 'AbortError')),
              { once: true },
            );
          }),
      );
      const client = createApiClient({
        baseUrl: 'http://127.0.0.1:8000',
        fetchImplementation,
      });

      const request = client.generateJobMatch('job-1', 'resume-1');
      const timeoutExpectation = expect(request).rejects.toThrow('JobPilot API request timed out');
      await vi.advanceTimersByTimeAsync(129_999);
      expect(fetchImplementation.mock.calls[0]?.[1]?.signal?.aborted).toBe(false);
      await vi.advanceTimersByTimeAsync(1);
      await timeoutExpectation;
    } finally {
      vi.useRealTimers();
    }
  });

  it('sends explicit consent without credentials and validates a match response', async () => {
    const fetchImplementation = vi.fn().mockImplementation(() => jsonResponse(matchResponse));
    const client = createApiClient({
      baseUrl: 'http://127.0.0.1:8000',
      fetchImplementation,
    });

    await expect(client.generateJobMatch('job-1', 'resume-1')).resolves.toEqual(matchResponse);

    const [url, init] = fetchImplementation.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('http://127.0.0.1:8000/api/v1/jobs/job-1/copilot/match');
    expect(init.credentials).toBe('omit');
    expect(init.redirect).toBe('error');
    expect(JSON.parse(String(init.body))).toEqual({
      resumeVersionId: 'resume-1',
      confirmExternalAi: true,
    });
  });

  it('uses the frozen read and generation routes for all three tools', async () => {
    const fetchImplementation = vi.fn().mockImplementation(() => jsonResponse(matchResponse));
    const client = createApiClient({
      baseUrl: 'http://127.0.0.1:8000',
      fetchImplementation,
    });

    await client.getJobMatch('job/1', 'resume 1');
    await client.getResumeAdvice('job/1', 'resume 1');
    await client.generateResumeAdvice('job/1', 'resume 1');
    await client.getInterviewPrep('job/1');
    await client.generateInterviewPrep('job/1');
    await client.getCopilotRecord('record/1');

    expect(fetchImplementation.mock.calls.map(([url]) => url)).toEqual([
      'http://127.0.0.1:8000/api/v1/jobs/job%2F1/copilot/match?resumeVersionId=resume+1',
      'http://127.0.0.1:8000/api/v1/jobs/job%2F1/copilot/resume-advice?resumeVersionId=resume+1',
      'http://127.0.0.1:8000/api/v1/jobs/job%2F1/copilot/resume-advice',
      'http://127.0.0.1:8000/api/v1/jobs/job%2F1/copilot/interview-prep',
      'http://127.0.0.1:8000/api/v1/jobs/job%2F1/copilot/interview-prep',
      'http://127.0.0.1:8000/api/v1/copilot/record%2F1',
    ]);
  });

  it('rejects malformed source evidence instead of rendering it', async () => {
    const malformed = structuredClone(matchResponse);
    malformed.record.result.strengths[0]!.sourceEvidence.sourceType = 'PROFILE';
    const client = createApiClient({
      baseUrl: 'http://127.0.0.1:8000',
      fetchImplementation: vi.fn().mockResolvedValue(jsonResponse(malformed)),
    });

    await expect(client.getJobMatch('job-1', 'resume-1')).rejects.toThrow(
      'invalid Copilot response',
    );
  });

  it('accepts schema v2 job-driven interview categories but keeps schema v1 strict', async () => {
    const response = {
      isConfigured: true,
      record: {
        ...matchResponse.record,
        kind: 'INTERVIEW_PREP',
        resumeVersionId: null,
        schemaVersion: 2,
        promptVersion: 'interview-prep-v2',
        result: {
          possibleQuestions: [
            {
              category: 'TECHNICAL',
              question: '如何处理安全事件？',
              reason: '岗位要求事件响应。',
              sourceEvidence: {
                text: '负责安全事件响应',
                sourceType: 'JOB',
                sourceId: 'job-1',
              },
            },
          ],
          review: { strengths: [], weaknesses: [], nextActions: [] },
        },
      },
    };
    const fetchImplementation = vi.fn().mockImplementation(() => jsonResponse(response));
    const client = createApiClient({
      baseUrl: 'http://127.0.0.1:8000',
      fetchImplementation,
    });

    await expect(client.getInterviewPrep('job-1')).resolves.toEqual(response);

    response.record.schemaVersion = 1;
    await expect(client.getInterviewPrep('job-1')).rejects.toThrow('invalid Copilot response');
  });
});

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}
