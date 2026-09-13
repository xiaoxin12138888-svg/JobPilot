import { useEffect, useState } from 'react';

import type {
  ApiClient,
  CopilotInterviewQuestion,
  CopilotRecord,
  CopilotResponse,
  GroundedCopilotItem,
  InterviewPrepResult,
  Job,
  JobAnalysisResponse,
  JobMatchResult,
  ResumeAdviceResult,
  ResumeVersion,
} from '@jobpilot/api-client';

type Tool = 'UNDERSTAND' | 'MATCH' | 'RESUME_ADVICE' | 'INTERVIEW_PREP';

const TOOLS: ReadonlyArray<{ id: Tool; label: string }> = [
  { id: 'UNDERSTAND', label: '岗位理解' },
  { id: 'MATCH', label: '匹配分析' },
  { id: 'RESUME_ADVICE', label: '简历准备' },
  { id: 'INTERVIEW_PREP', label: '面试准备' },
];

interface CopilotPanelProps {
  apiClient: ApiClient;
  job: Job;
  analysisState: JobAnalysisResponse | null | undefined;
  resumeVersions: ResumeVersion[];
  resumeLoadError: string | undefined;
}

interface CopilotLoadState {
  requestKey: string;
  response?: CopilotResponse;
  error?: string;
}

export function CopilotPanel({
  apiClient,
  job,
  analysisState,
  resumeVersions,
  resumeLoadError,
}: CopilotPanelProps) {
  const [tool, setTool] = useState<Tool>('UNDERSTAND');
  const [selectedResumeId, setSelectedResumeId] = useState('');
  const [loadState, setLoadState] = useState<CopilotLoadState>();
  const [generating, setGenerating] = useState(false);
  const [generationError, setGenerationError] = useState<string>();
  const [reloadToken, setReloadToken] = useState(0);

  const analysis = analysisState?.analysis;
  const needsResume = tool === 'MATCH' || tool === 'RESUME_ADVICE';
  const canLoad = tool !== 'UNDERSTAND' && (!needsResume || Boolean(selectedResumeId));
  const canGenerate = canLoad && Boolean(analysis && !analysis.isStale);
  const requestKey = canLoad
    ? [job.id, tool, selectedResumeId, String(reloadToken)].join(':')
    : undefined;
  const currentLoadState = loadState?.requestKey === requestKey ? loadState : undefined;
  const response = currentLoadState?.response;
  const loadError = currentLoadState?.error;
  const loading = requestKey !== undefined && currentLoadState === undefined;

  useEffect(() => {
    if (!requestKey) return;
    let active = true;
    const request =
      tool === 'MATCH'
        ? apiClient.getJobMatch(job.id, selectedResumeId)
        : tool === 'RESUME_ADVICE'
          ? apiClient.getResumeAdvice(job.id, selectedResumeId)
          : apiClient.getInterviewPrep(job.id);
    void request
      .then((value) => {
        if (active) setLoadState({ requestKey, response: value });
      })
      .catch(() => {
        if (active) {
          setLoadState({ requestKey, error: 'Copilot 结果暂时无法读取，请稍后重试。' });
        }
      });
    return () => {
      active = false;
    };
  }, [apiClient, job.id, requestKey, selectedResumeId, tool]);

  async function generate() {
    if (tool === 'UNDERSTAND' || !canGenerate || !requestKey || generating) return;
    const confirmed = window.confirm(
      tool === 'INTERVIEW_PREP'
        ? '本次生成会将当前岗位条件与已有面试记录（已移除联系方式）发送至你配置的 AI 服务。是否继续？'
        : '本次生成会将当前岗位条件与所选简历正文（已移除联系方式）发送至你配置的 AI 服务。是否继续？',
    );
    if (!confirmed) return;
    setGenerating(true);
    setGenerationError(undefined);
    try {
      const value =
        tool === 'MATCH'
          ? await apiClient.generateJobMatch(job.id, selectedResumeId)
          : tool === 'RESUME_ADVICE'
            ? await apiClient.generateResumeAdvice(job.id, selectedResumeId)
            : await apiClient.generateInterviewPrep(job.id);
      setLoadState({ requestKey, response: value });
    } catch {
      setGenerationError('AI Copilot 暂时不可用，请稍后重试。');
    } finally {
      setGenerating(false);
    }
  }

  const record = response?.record;
  const action = actionLabel(tool, Boolean(record));

  return (
    <section className="content-card copilot-card" aria-labelledby="copilot-title">
      <div className="analysis-header">
        <div>
          <p className="eyebrow">OPTIONAL AI · USER CONTROLLED</p>
          <h2 id="copilot-title">AI 求职 Copilot</h2>
        </div>
        {canGenerate && response?.isConfigured && (
          <button
            type="button"
            className="button primary"
            disabled={generating || loading}
            onClick={() => void generate()}
          >
            {generating ? '正在分析…' : action}
          </button>
        )}
      </div>

      <div className="copilot-tabs" role="toolbar" aria-label="Copilot 工具">
        {TOOLS.map((item) => (
          <button
            type="button"
            key={item.id}
            className={tool === item.id ? 'copilot-tab active' : 'copilot-tab'}
            aria-pressed={tool === item.id}
            onClick={() => {
              setTool(item.id);
              setGenerationError(undefined);
            }}
          >
            {item.label}
          </button>
        ))}
      </div>

      {needsResume && (
        <label className="field evidence-resume-select">
          <span>用于 Copilot 的简历版本</span>
          <select
            value={selectedResumeId}
            disabled={Boolean(resumeLoadError) || resumeVersions.length === 0 || generating}
            onChange={(event) => {
              setSelectedResumeId(event.target.value);
              setGenerationError(undefined);
            }}
          >
            <option value="">请选择</option>
            {resumeVersions.map((resume) => (
              <option value={resume.id} key={resume.id}>
                {resume.name}
              </option>
            ))}
          </select>
        </label>
      )}

      {tool === 'UNDERSTAND' ? (
        <JobUnderstanding analysisState={analysisState} />
      ) : resumeLoadError && needsResume ? (
        <Message kind="error">{resumeLoadError}</Message>
      ) : needsResume && resumeVersions.length === 0 ? (
        <Message>请先创建一个简历版本，再使用匹配分析或简历准备。</Message>
      ) : needsResume && !selectedResumeId ? (
        <Message>请选择一个简历版本。只有你点击并确认后，必要文本才会发送给 AI。</Message>
      ) : loading ? (
        <p className="muted" role="status">
          正在读取 Copilot 结果…
        </p>
      ) : loadError ? (
        <div className="analysis-error" role="alert">
          <p>{loadError}</p>
          <button
            type="button"
            className="text-button"
            onClick={() => setReloadToken((value) => value + 1)}
          >
            重试读取
          </button>
        </div>
      ) : (
        <>
          {analysisState === undefined ? (
            <p className="muted" role="status">
              正在读取岗位分析…
            </p>
          ) : analysisState === null ? (
            <Message kind="error">
              岗位分析状态暂时无法读取；历史结果仍可查看，但暂时不能生成。
            </Message>
          ) : !analysis ? (
            <Message>请先完成岗位 AI 分析。历史结果仍可查看。</Message>
          ) : analysis.isStale ? (
            <p className="analysis-stale" role="status">
              岗位描述已变化，请先重新分析 JD 后再生成。
            </p>
          ) : null}
          {response && !response.isConfigured && (
            <Message>AI 服务未配置。历史结果与岗位、简历、投递和面试记录仍可正常使用。</Message>
          )}
          {generationError && <Message kind="error">{generationError}</Message>}
          {!record && response?.isConfigured && canGenerate && (
            <Message>尚未生成。点击上方按钮并确认后，JobPilot 才会请求 AI 服务。</Message>
          )}
          {record && (
            <>
              {record.isStale && (
                <p className="analysis-stale" role="status">
                  {tool === 'INTERVIEW_PREP'
                    ? '岗位或面试记录已更新，当前结果已过期。'
                    : '岗位或简历内容已更新，当前结果已过期。'}
                </p>
              )}
              <CopilotResult record={record} />
            </>
          )}
        </>
      )}
    </section>
  );
}

function JobUnderstanding({
  analysisState,
}: {
  analysisState: JobAnalysisResponse | null | undefined;
}) {
  if (analysisState === undefined) return <p className="muted">正在读取岗位分析…</p>;
  if (analysisState === null) return <Message kind="error">岗位分析暂时无法读取。</Message>;
  const analysis = analysisState.analysis;
  if (!analysis) return <Message>请先完成岗位 AI 分析，岗位理解会复用已验证的结构化结果。</Message>;
  return (
    <div className="copilot-result">
      <p className="source-pill source-job">来自岗位</p>
      {analysis.isStale && <p className="analysis-stale">岗位信息已变化，当前理解可能已过期。</p>}
      <section className="copilot-section">
        <h3>岗位摘要</h3>
        <p>{analysis.result.summary || 'JD 未明确说明。'}</p>
      </section>
      <section className="copilot-section">
        <h3>主要条件</h3>
        {analysis.result.mustHaveRequirements.length ? (
          <ul>
            {analysis.result.mustHaveRequirements.map((item) => (
              <li key={item.text}>{item.text}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">JD 未明确说明硬性条件。</p>
        )}
      </section>
    </div>
  );
}

function CopilotResult({ record }: { record: CopilotRecord }) {
  return (
    <div className="copilot-result">
      <div className="copilot-generated-meta">
        <strong>AI 生成内容</strong>
        <span>{formatDate(record.createdAt)}</span>
      </div>
      {record.kind === 'MATCH' ? (
        <MatchView result={record.result as JobMatchResult} />
      ) : record.kind === 'RESUME_ADVICE' ? (
        <ResumeAdviceView result={record.result as ResumeAdviceResult} />
      ) : (
        <InterviewPrepView result={record.result as InterviewPrepResult} />
      )}
    </div>
  );
}

function MatchView({ result }: { result: JobMatchResult }) {
  return (
    <>
      <section className="copilot-section">
        <h3>综合判断</h3>
        <p>{result.summary}</p>
      </section>
      <GroundedSection title="真实优势" items={result.strengths} />
      <GroundedSection title="当前证据差距" items={result.gaps} />
      <AdviceSection title="下一步建议" items={result.suggestions} />
    </>
  );
}

function ResumeAdviceView({ result }: { result: ResumeAdviceResult }) {
  return (
    <>
      <GroundedSection title="值得强调" items={result.highlight} />
      <AdviceSection title="可改进方向" items={result.possibleImprovement} />
      <GroundedSection title="面试准备重点" items={result.interviewFocus} />
    </>
  );
}

function InterviewPrepView({ result }: { result: InterviewPrepResult }) {
  return (
    <>
      <section className="copilot-section">
        <h3>可能关注方向</h3>
        <div className="copilot-question-list">
          {result.possibleQuestions.map((item, index) => (
            <InterviewQuestionView item={item} key={`${item.category}-${index}`} />
          ))}
        </div>
      </section>
      <GroundedSection title="复盘中的优势" items={result.review.strengths} />
      <GroundedSection title="复盘中的待改进" items={result.review.weaknesses} />
      <AdviceSection title="后续行动" items={result.review.nextActions} />
    </>
  );
}

function InterviewQuestionView({ item }: { item: CopilotInterviewQuestion }) {
  return (
    <article className="copilot-evidence-item">
      <span className="question-category">{item.category}</span>
      <h4>{item.question}</h4>
      <p>{item.reason}</p>
      <Evidence evidence={item.sourceEvidence} />
    </article>
  );
}

function GroundedSection({ title, items }: { title: string; items: GroundedCopilotItem[] }) {
  return (
    <section className="copilot-section">
      <h3>{title}</h3>
      {items.length ? (
        <div className="copilot-evidence-list">
          {items.map((item, index) => (
            <article className="copilot-evidence-item" key={`${item.text}-${index}`}>
              <p>{item.text}</p>
              <Evidence evidence={item.sourceEvidence} />
            </article>
          ))}
        </div>
      ) : (
        <p className="muted">当前资料未发现可展示的内容。</p>
      )}
    </section>
  );
}

function Evidence({ evidence }: { evidence: GroundedCopilotItem['sourceEvidence'] }) {
  const label =
    evidence.sourceType === 'RESUME'
      ? '来自简历'
      : evidence.sourceType === 'INTERVIEW'
        ? '来自面试'
        : '来自岗位';
  return (
    <div className="copilot-evidence">
      <span className={`source-pill source-${evidence.sourceType.toLowerCase()}`}>{label}</span>
      <blockquote>{evidence.text}</blockquote>
    </div>
  );
}

function AdviceSection({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="copilot-section">
      <h3>{title}</h3>
      <span className="source-pill source-advice">AI建议</span>
      {items.length ? (
        <ul>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">暂无建议。</p>
      )}
    </section>
  );
}

function Message({ children, kind }: { children: string; kind?: 'error' }) {
  return (
    <div className={kind ? 'analysis-error' : 'analysis-empty'} role={kind ? 'alert' : undefined}>
      <p>{children}</p>
    </div>
  );
}

function actionLabel(tool: Tool, exists: boolean): string {
  if (tool === 'MATCH') return exists ? '重新生成匹配分析' : '生成匹配分析';
  if (tool === 'RESUME_ADVICE') return exists ? '重新生成简历建议' : '生成简历建议';
  return exists ? '重新生成面试准备' : '生成面试准备';
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(value),
  );
}
