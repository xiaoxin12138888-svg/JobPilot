import { useEffect, useState } from 'react';

import type {
  ApiClient,
  EvidenceItem,
  JDAnalysis,
  Job,
  JobAnalysisResponse,
} from '@jobpilot/api-client';

interface JDAnalysisPanelProps {
  apiClient: ApiClient;
  job: Job;
  onStateChange?(state: JobAnalysisResponse | null | undefined): void;
}

export function JDAnalysisPanel({ apiClient, job, onStateChange }: JDAnalysisPanelProps) {
  const [state, setState] = useState<JobAnalysisResponse>();
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [loadError, setLoadError] = useState<string>();
  const [analysisError, setAnalysisError] = useState<string>();
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let active = true;
    void apiClient
      .getJobAnalysis(job.id)
      .then((response) => {
        if (active) {
          setState(response);
          onStateChange?.(response);
        }
      })
      .catch(() => {
        if (active) {
          setLoadError('AI 分析状态暂时无法读取，请稍后重试。');
          onStateChange?.(null);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [apiClient, job.id, onStateChange, reloadToken]);

  const retryLoad = () => {
    setLoadError(undefined);
    setLoading(true);
    onStateChange?.(undefined);
    setReloadToken((value) => value + 1);
  };

  const analyze = async () => {
    setAnalyzing(true);
    setAnalysisError(undefined);
    try {
      const response = await apiClient.analyzeJob(job.id);
      setState(response);
      onStateChange?.(response);
    } catch {
      setAnalysisError('AI 分析暂时不可用，请稍后重试。');
    } finally {
      setAnalyzing(false);
    }
  };

  const analysis = state?.analysis;
  const actionLabel = analysis ? '重新分析' : 'AI 分析此岗位';

  return (
    <section className="content-card analysis-card" aria-labelledby="jd-analysis-title">
      <div className="analysis-header">
        <div>
          <p className="eyebrow">OPTIONAL AI</p>
          <h2 id="jd-analysis-title">AI 岗位分析</h2>
        </div>
        {!loading && state?.isConfigured && job.description && (
          <button
            type="button"
            className="button primary"
            disabled={analyzing}
            onClick={() => void analyze()}
          >
            {analyzing ? '分析中…' : actionLabel}
          </button>
        )}
      </div>

      {loading && (
        <p className="muted" role="status">
          正在读取 AI 分析…
        </p>
      )}
      {loadError && (
        <div className="analysis-error" role="alert">
          <p>{loadError}</p>
          <button type="button" className="text-button" onClick={retryLoad}>
            重试读取
          </button>
        </div>
      )}
      {analysisError && (
        <div className="analysis-error" role="alert">
          <p>{analysisError}</p>
        </div>
      )}
      {!loading && !loadError && state && !state.isConfigured && (
        <div className="analysis-empty">
          <strong>AI 服务未配置</strong>
          <p>配置本机 FastAPI 的模型环境变量后，可按需分析此岗位；其他功能不受影响。</p>
        </div>
      )}
      {!loading && !loadError && state?.isConfigured && !job.description && (
        <p className="muted">尚未填写 JD，无法进行结构化分析。</p>
      )}
      {!loading && !loadError && state?.isConfigured && job.description && !analysis && (
        <div className="analysis-empty">
          <strong>尚未分析</strong>
          <p>仅在你点击按钮后，必要的岗位字段才会发送到已配置的模型服务。</p>
        </div>
      )}
      {analysis && (
        <>
          {analysis.isStale && (
            <p className="analysis-stale" role="status">
              岗位信息已修改，当前分析可能已过期。
            </p>
          )}
          <AnalysisResult result={analysis.result} />
        </>
      )}
    </section>
  );
}

function AnalysisResult({ result }: { result: JDAnalysis }) {
  return (
    <div className="analysis-result">
      <AnalysisText title="岗位摘要" value={result.summary} />
      <AnalysisItems title="核心职责" items={result.responsibilities} />
      <AnalysisItems title="硬性要求" items={result.mustHaveRequirements} />
      <AnalysisItems title="加分项" items={result.preferredRequirements} />
      <AnalysisTags title="技能关键词" items={result.skills} />
      <AnalysisItems title="经验要求" items={result.experienceRequirements} />
      <AnalysisItems title="学历要求" items={result.educationRequirements} />
      <AnalysisTags title="业务 / 领域关键词" items={result.domainKeywords} />
      <AnalysisItems title="面试准备重点" items={result.interviewFocus} />
    </div>
  );
}

function AnalysisText({ title, value }: { title: string; value: string }) {
  return (
    <section className="analysis-section">
      <h3>{title}</h3>
      <p className={value ? undefined : 'muted'}>{value || 'JD 未明确说明。'}</p>
    </section>
  );
}

function AnalysisItems({ title, items }: { title: string; items: EvidenceItem[] }) {
  return (
    <section className="analysis-section">
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p className="muted">JD 未明确说明。</p>
      ) : (
        <ul className="analysis-list">
          {items.map((item, index) => (
            <li key={`${item.text}-${index}`}>
              <span>{item.text}</span>
              {item.evidence && (
                <details className="analysis-evidence">
                  <summary>查看原文依据</summary>
                  <blockquote>{item.evidence}</blockquote>
                </details>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function AnalysisTags({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="analysis-section">
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p className="muted">JD 未明确说明。</p>
      ) : (
        <div className="analysis-tags">
          {items.map((item) => (
            <span className="analysis-tag" key={item}>
              {item}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
