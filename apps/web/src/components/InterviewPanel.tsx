import { useEffect, useState } from 'react';

import { INTERVIEW_STATUS_LABELS, INTERVIEW_TYPE_LABELS } from '@jobpilot/api-client';
import type {
  ApiClient,
  Application,
  CreateInterviewRoundInput,
  InterviewRound,
  InterviewType,
} from '@jobpilot/api-client';

interface InterviewPanelProps {
  apiClient: ApiClient;
  application: Application | undefined;
}

export function InterviewPanel({ apiClient, application }: InterviewPanelProps) {
  const applicationId = application?.id;
  const [interviews, setInterviews] = useState<InterviewRound[]>([]);
  const [loading, setLoading] = useState(Boolean(applicationId));
  const [error, setError] = useState<string>();
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!applicationId) return;
    let active = true;
    void apiClient
      .listInterviews(applicationId)
      .then(
        (response) => {
          if (active) setInterviews(response.items);
        },
        () => {
          if (active) setError('面试记录暂时无法读取，请稍后重试。');
        },
      )
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [apiClient, applicationId]);

  async function createInterview(input: CreateInterviewRoundInput) {
    if (!application) return;
    setError(undefined);
    try {
      const created = await apiClient.createInterview(application.id, input);
      setInterviews((current) => [...current, created]);
      setCreating(false);
    } catch {
      setError('面试记录保存失败，请稍后重试。');
    }
  }

  return (
    <section className="content-card interview-panel" aria-labelledby="interview-panel-title">
      <div className="section-heading-row">
        <div>
          <p className="eyebrow">INTERVIEW</p>
          <h2 id="interview-panel-title">面试记录</h2>
        </div>
        {application && !creating && (
          <button type="button" className="button secondary" onClick={() => setCreating(true)}>
            添加面试
          </button>
        )}
      </div>

      {!application ? (
        <p className="muted">建立投递后，可以按轮次记录面试过程。</p>
      ) : loading ? (
        <p className="loading-state" role="status">
          正在加载面试记录…
        </p>
      ) : (
        <>
          {interviews.length === 0 && !creating && (
            <div className="analysis-empty">
              <strong>还没有面试记录</strong>
              <p>添加一轮面试，记录真实问题和你的复盘。</p>
            </div>
          )}
          {creating && (
            <InterviewCreateForm onCancel={() => setCreating(false)} onSubmit={createInterview} />
          )}
          {interviews.length > 0 && (
            <div className="interview-list">
              {interviews.map((interview) => (
                <article className="interview-round" key={interview.id}>
                  <div>
                    <h3>{interview.roundName}</h3>
                    <p className="muted">
                      {INTERVIEW_TYPE_LABELS[interview.interviewType]} ·{' '}
                      {INTERVIEW_STATUS_LABELS[interview.status]} · {interview.questions.length}{' '}
                      道面试题
                    </p>
                  </div>
                  {interview.scheduledAt && <time>{formatDate(interview.scheduledAt)}</time>}
                </article>
              ))}
            </div>
          )}
        </>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

function InterviewCreateForm({
  onCancel,
  onSubmit,
}: {
  onCancel(): void;
  onSubmit(input: CreateInterviewRoundInput): Promise<void>;
}) {
  const [roundName, setRoundName] = useState('');
  const [interviewType, setInterviewType] = useState<InterviewType>('VIDEO');
  const [scheduledAt, setScheduledAt] = useState('');
  const [interviewerNote, setInterviewerNote] = useState('');
  const [saving, setSaving] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!roundName.trim()) return;
    setSaving(true);
    await onSubmit({
      roundName: roundName.trim(),
      interviewType,
      scheduledAt: scheduledAt ? new Date(scheduledAt).toISOString() : null,
      interviewerNote: interviewerNote.trim() || null,
    });
    setSaving(false);
  }

  return (
    <form className="interview-form" onSubmit={(event) => void submit(event)}>
      <label className="field">
        <span>轮次名称 *</span>
        <input value={roundName} required onChange={(event) => setRoundName(event.target.value)} />
      </label>
      <label className="field">
        <span>面试类型</span>
        <select
          value={interviewType}
          onChange={(event) => setInterviewType(event.target.value as InterviewType)}
        >
          {Object.entries(INTERVIEW_TYPE_LABELS).map(([value, label]) => (
            <option value={value} key={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>计划时间</span>
        <input
          type="datetime-local"
          value={scheduledAt}
          onChange={(event) => setScheduledAt(event.target.value)}
        />
      </label>
      <label className="field interview-form-wide">
        <span>面试官备注</span>
        <textarea
          value={interviewerNote}
          onChange={(event) => setInterviewerNote(event.target.value)}
        />
      </label>
      <div className="form-actions interview-form-wide">
        <button type="button" className="button secondary" onClick={onCancel}>
          取消
        </button>
        <button type="submit" className="button primary" disabled={saving || !roundName.trim()}>
          {saving ? '正在保存…' : '保存面试'}
        </button>
      </div>
    </form>
  );
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(value),
  );
}
