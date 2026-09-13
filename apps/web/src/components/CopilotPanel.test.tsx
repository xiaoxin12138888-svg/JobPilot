import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ApiClient, CopilotResponse, Job, JobAnalysisResponse } from '@jobpilot/api-client';

import { CopilotPanel } from './CopilotPanel';

describe('CopilotPanel', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('keeps four focused tools and renders grounded match evidence with AI advice', async () => {
    let finish: ((value: CopilotResponse) => void) | undefined;
    const generation = new Promise<CopilotResponse>((resolve) => {
      finish = resolve;
    });
    const apiClient = partialClient({
      getJobMatch: vi.fn().mockResolvedValue({ isConfigured: true, record: null }),
      generateJobMatch: vi.fn().mockReturnValue(generation),
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(
      <CopilotPanel
        apiClient={apiClient}
        job={job}
        analysisState={analysisState}
        resumeVersions={[resume]}
        resumeLoadError={undefined}
      />,
    );

    const panel = screen.getByRole('region', { name: 'AI 求职 Copilot' });
    for (const tab of ['岗位理解', '匹配分析', '简历准备', '面试准备']) {
      expect(within(panel).getByRole('button', { name: tab })).toBeInTheDocument();
    }
    fireEvent.click(within(panel).getByRole('button', { name: '匹配分析' }));
    fireEvent.change(within(panel).getByLabelText('用于 Copilot 的简历版本'), {
      target: { value: resume.id },
    });
    fireEvent.click(await within(panel).findByRole('button', { name: '生成匹配分析' }));

    expect(window.confirm).toHaveBeenCalled();
    expect(within(panel).getByRole('button', { name: '正在分析…' })).toBeDisabled();

    await act(async () => finish?.(matchResponse));
    expect(await within(panel).findByText('AI 生成内容')).toBeInTheDocument();
    expect(within(panel).getByText('来自简历')).toBeInTheDocument();
    expect(within(panel).getByText('来自岗位')).toBeInTheDocument();
    expect(within(panel).getByText('AI建议')).toBeInTheDocument();
    expect(within(panel).getByText('已有需求分析经历。')).toBeInTheDocument();
    expect(within(panel).getByText('参与需求分析')).toBeInTheDocument();
  });

  it('keeps a stale result visible after a failed regeneration', async () => {
    const stale = structuredClone(matchResponse);
    stale.record!.isStale = true;
    const apiClient = partialClient({
      getJobMatch: vi.fn().mockResolvedValue(stale),
      generateJobMatch: vi.fn().mockRejectedValue(new Error('raw provider response')),
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(
      <CopilotPanel
        apiClient={apiClient}
        job={job}
        analysisState={analysisState}
        resumeVersions={[resume]}
        resumeLoadError={undefined}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '匹配分析' }));
    fireEvent.change(screen.getByLabelText('用于 Copilot 的简历版本'), {
      target: { value: resume.id },
    });
    expect(await screen.findByText('岗位或简历内容已更新，当前结果已过期。')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重新生成匹配分析' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'AI Copilot 暂时不可用，请稍后重试。',
    );
    expect(screen.getByText('已有需求分析经历。')).toBeInTheDocument();
    expect(screen.queryByText('raw provider response')).toBeNull();
  });

  it('keeps historical results readable when the JD analysis becomes stale', async () => {
    const staleAnalysis = structuredClone(analysisState);
    staleAnalysis.analysis!.isStale = true;
    const stale = structuredClone(matchResponse);
    stale.record!.isStale = true;
    const getJobMatch = vi.fn().mockResolvedValue(stale);

    render(
      <CopilotPanel
        apiClient={partialClient({ getJobMatch })}
        job={job}
        analysisState={staleAnalysis}
        resumeVersions={[resume]}
        resumeLoadError={undefined}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '匹配分析' }));
    fireEvent.change(screen.getByLabelText('用于 Copilot 的简历版本'), {
      target: { value: resume.id },
    });

    expect(await screen.findByText('已有需求分析经历。')).toBeInTheDocument();
    expect(screen.getByText('岗位或简历内容已更新，当前结果已过期。')).toBeInTheDocument();
    expect(screen.getByText('岗位描述已变化，请先重新分析 JD 后再生成。')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '重新生成匹配分析' })).toBeNull();
    expect(getJobMatch).toHaveBeenCalledWith(job.id, resume.id);
  });
});

function partialClient(overrides: Partial<ApiClient>): ApiClient {
  return overrides as ApiClient;
}

const job: Job = {
  id: 'job-1',
  title: 'AI 产品经理',
  company: '虚构公司',
  location: null,
  salaryText: null,
  source: 'manual',
  sourceUrl: null,
  description: '负责需求分析',
  notes: null,
  createdAt: '2026-09-09T00:00:00Z',
  updatedAt: '2026-09-09T00:00:00Z',
};

const resume = {
  id: 'resume-1',
  name: '产品简历',
  content: '参与需求分析',
  applicationCount: 0,
  createdAt: '2026-09-09T00:00:00Z',
  updatedAt: '2026-09-09T00:00:00Z',
};

const analysisState: JobAnalysisResponse = {
  isConfigured: true,
  analysis: {
    id: 'analysis-1',
    jobId: job.id,
    schemaVersion: 1,
    result: {
      summary: '负责 AI 产品需求分析。',
      responsibilities: [],
      mustHaveRequirements: [{ text: '熟练使用 SQL', evidence: '熟练使用 SQL' }],
      preferredRequirements: [],
      skills: [],
      experienceRequirements: [],
      educationRequirements: [],
      domainKeywords: [],
      interviewFocus: [],
    },
    isStale: false,
    createdAt: '2026-09-09T00:00:00Z',
    updatedAt: '2026-09-09T00:00:00Z',
  },
};

const matchResponse: CopilotResponse = {
  isConfigured: true,
  record: {
    id: 'copilot-1',
    jobId: job.id,
    resumeVersionId: resume.id,
    kind: 'MATCH',
    schemaVersion: 1,
    result: {
      summary: '当前经历与岗位有相关证据。',
      strengths: [
        {
          text: '已有需求分析经历。',
          sourceEvidence: {
            text: '参与需求分析',
            sourceType: 'RESUME',
            sourceId: resume.id,
          },
        },
      ],
      gaps: [
        {
          text: '当前简历未发现 SQL 实践证据。',
          sourceEvidence: {
            text: '熟练使用 SQL',
            sourceType: 'JOB',
            sourceId: job.id,
          },
        },
      ],
      suggestions: ['准备一个可验证的数据分析案例。'],
    },
    inputFingerprint: 'a'.repeat(64),
    model: 'fictional-model',
    promptVersion: 'match-v1',
    isStale: false,
    createdAt: '2026-09-09T00:00:00Z',
  },
};
