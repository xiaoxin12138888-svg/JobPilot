import { useEffect, useState } from 'react';

import type {
  ApiClient,
  Job,
  JobAnalysisResponse,
  JobEvidenceMapResponse,
  ResumeVersion,
} from '@jobpilot/api-client';

import { EvidenceMapResult } from './EvidenceMapResult';

interface EvidenceMapPanelProps {
  apiClient: ApiClient;
  job: Job;
  analysisState: JobAnalysisResponse | null | undefined;
  resumeVersions: ResumeVersion[];
  resumeLoadError: string | undefined;
}

export function EvidenceMapPanel({
  apiClient,
  job,
  analysisState,
  resumeVersions,
  resumeLoadError,
}: EvidenceMapPanelProps) {
  const [selectedResumeId, setSelectedResumeId] = useState('');
  const [loaded, setLoaded] = useState<{
    requestKey: string;
    response: JobEvidenceMapResponse;
  }>();
  const [generating, setGenerating] = useState(false);
  const [loadFailure, setLoadFailure] = useState<{ requestKey: string; message: string }>();
  const [generationFailure, setGenerationFailure] = useState<{
    requestKey: string;
    message: string;
  }>();
  const [reloadToken, setReloadToken] = useState(0);

  const analysis = analysisState?.analysis;
  const requestKey =
    selectedResumeId && analysis && !analysis.isStale
      ? [job.id, selectedResumeId, analysis.id, analysis.updatedAt, reloadToken].join(':')
      : undefined;

  useEffect(() => {
    if (!selectedResumeId || !requestKey) return;
    let active = true;
    void apiClient
      .getJobEvidenceMap(job.id, selectedResumeId)
      .then((response) => {
        if (active) setLoaded({ requestKey, response });
      })
      .catch(() => {
        if (active) {
          setLoadFailure({
            requestKey,
            message: '证据映射状态暂时无法读取，请稍后重试。',
          });
        }
      });
    return () => {
      active = false;
    };
  }, [apiClient, job.id, requestKey, selectedResumeId]);

  async function generate() {
    if (!selectedResumeId || !requestKey) return;
    const confirmed = window.confirm(
      '本次分析会将当前选择的简历正文与岗位的六类结构化条件发送至你配置的 AI 服务，用于综合证据判断。是否继续？',
    );
    if (!confirmed) return;
    setGenerating(true);
    setGenerationFailure(undefined);
    try {
      const response = await apiClient.generateJobEvidenceMap(job.id, selectedResumeId);
      setLoaded({ requestKey, response });
    } catch {
      setGenerationFailure({
        requestKey,
        message: 'AI证据匹配暂时不可用，请稍后重试。',
      });
    } finally {
      setGenerating(false);
    }
  }

  const state = loaded && loaded.requestKey === requestKey ? loaded.response : undefined;
  const loadError =
    loadFailure && loadFailure.requestKey === requestKey ? loadFailure.message : undefined;
  const generationError =
    generationFailure && generationFailure.requestKey === requestKey
      ? generationFailure.message
      : undefined;
  const loading = Boolean(requestKey && !state && !loadError);
  const evidenceMap = state?.evidenceMap;
  const actionLabel = evidenceMap ? '重新生成证据映射' : '生成证据映射';

  return (
    <section className="content-card evidence-map-card" aria-labelledby="evidence-map-title">
      <div className="analysis-header">
        <div>
          <p className="eyebrow">RESUME EVIDENCE</p>
          <h2 id="evidence-map-title">简历综合证据分析</h2>
        </div>
        {selectedResumeId && analysis && !analysis.isStale && state?.isConfigured && (
          <button
            type="button"
            className="button primary"
            disabled={generating || loading}
            onClick={() => void generate()}
          >
            {generating ? '正在综合分析岗位条件与简历证据…' : actionLabel}
          </button>
        )}
      </div>

      <label className="field evidence-resume-select">
        <span>用于证据匹配的简历版本</span>
        <select
          value={selectedResumeId}
          disabled={Boolean(resumeLoadError) || resumeVersions.length === 0 || generating}
          onChange={(event) => {
            setSelectedResumeId(event.target.value);
            setGenerationFailure(undefined);
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

      {resumeLoadError ? (
        <div className="analysis-error" role="alert">
          <p>{resumeLoadError}</p>
        </div>
      ) : resumeVersions.length === 0 ? (
        <div className="analysis-empty">
          <strong>请先创建简历版本</strong>
          <p>在“简历版本”页面粘贴纯文本正文后，再回到岗位详情进行证据匹配。</p>
        </div>
      ) : !selectedResumeId ? (
        <div className="analysis-empty">
          <strong>请选择一个简历版本</strong>
          <p>Evidence Map 不会自动选择本次投递版本，也不会自动发送任何简历内容。</p>
        </div>
      ) : analysisState === undefined ? (
        <p className="muted" role="status">
          正在读取岗位分析…
        </p>
      ) : analysisState === null ? (
        <div className="analysis-error" role="alert">
          <p>岗位分析状态暂时无法读取，请稍后重试。</p>
        </div>
      ) : !analysis ? (
        <div className="analysis-empty">
          <strong>请先完成岗位 AI 分析。</strong>
          <p>Evidence Map 使用当前结构化分析中的硬性要求、加分项、职责、技能、经验与学历条件。</p>
        </div>
      ) : analysis.isStale ? (
        <p className="analysis-stale" role="status">
          岗位描述已变化，请先重新分析 JD。
        </p>
      ) : loading ? (
        <p className="muted" role="status">
          正在读取证据映射…
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
      ) : state && !state.isConfigured ? (
        <div className="analysis-empty">
          <strong>AI 服务未配置</strong>
          <p>简历版本与投递关联仍可正常使用；配置模型服务后再按需生成证据映射。</p>
        </div>
      ) : (
        <>
          {generationError && (
            <div className="analysis-error" role="alert">
              <p>{generationError}</p>
            </div>
          )}
          {!evidenceMap && state?.isConfigured && (
            <div className="analysis-empty">
              <strong>尚未生成证据映射</strong>
              <p>只有你点击并确认后，当前简历正文与六类岗位条件才会发送到已配置的 AI 服务。</p>
            </div>
          )}
          {evidenceMap && (
            <>
              {evidenceMap.isStale && (
                <p className="analysis-stale" role="status">
                  岗位或简历内容已更新，请重新生成证据映射。
                </p>
              )}
              <EvidenceMapResult mappings={evidenceMap.result.mappings} />
            </>
          )}
        </>
      )}
    </section>
  );
}
