import { useState } from 'react';

import { INTERVIEW_STATUS_LABELS, INTERVIEW_TYPE_LABELS } from '@jobpilot/api-client';
import type { ApiClient, CreateInterviewRoundInput, InterviewRound } from '@jobpilot/api-client';

import { InterviewRoundForm } from './InterviewRoundForm';

export function InterviewRoundCard({
  apiClient,
  interview,
  onUpdate,
  onDelete,
}: {
  apiClient: ApiClient;
  interview: InterviewRound;
  onUpdate(interview: InterviewRound): void;
  onDelete(interviewId: string): void;
}) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  async function update(input: CreateInterviewRoundInput) {
    setError(undefined);
    try {
      onUpdate(await apiClient.updateInterview(interview.id, input));
      setEditing(false);
    } catch {
      setError('面试记录更新失败，请稍后重试。');
    }
  }

  async function complete() {
    setBusy(true);
    setError(undefined);
    try {
      onUpdate(await apiClient.updateInterview(interview.id, { status: 'COMPLETED' }));
    } catch {
      setError('面试状态更新失败，请稍后重试。');
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm('删除该轮面试及其题目记录？')) return;
    setBusy(true);
    setError(undefined);
    try {
      await apiClient.deleteInterview(interview.id);
      onDelete(interview.id);
    } catch {
      setError('面试记录删除失败，请稍后重试。');
      setBusy(false);
    }
  }

  return (
    <article className="interview-round" aria-labelledby={`interview-${interview.id}`}>
      <div className="interview-round-header">
        <div>
          <h3 id={`interview-${interview.id}`}>{interview.roundName}</h3>
          <p className="muted">
            {INTERVIEW_TYPE_LABELS[interview.interviewType]} ·{' '}
            <span className={`round-status round-status-${interview.status.toLowerCase()}`}>
              {INTERVIEW_STATUS_LABELS[interview.status]}
            </span>{' '}
            · {interview.questions.length} 道面试题
          </p>
          {interview.scheduledAt && <time>{formatDate(interview.scheduledAt)}</time>}
        </div>
        <div className="compact-actions">
          <button type="button" className="text-button" onClick={() => setEditing(true)}>
            编辑与复盘
          </button>
          {interview.status !== 'COMPLETED' && (
            <button
              type="button"
              className="text-button"
              disabled={busy}
              onClick={() => void complete()}
            >
              标记完成
            </button>
          )}
          <button
            type="button"
            className="text-button danger-text"
            disabled={busy}
            onClick={() => void remove()}
          >
            删除面试
          </button>
        </div>
      </div>
      {editing && (
        <InterviewRoundForm
          initial={interview}
          submitLabel="保存面试修改"
          onCancel={() => setEditing(false)}
          onSubmit={update}
        />
      )}
      {!editing && <ReviewSummary interview={interview} />}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </article>
  );
}

function ReviewSummary({ interview }: { interview: InterviewRound }) {
  const items = [
    ['做得好的地方', interview.wentWell],
    ['没答好的地方', interview.couldImprove],
    ['需要补充学习', interview.learningNotes],
    ['其他备注', interview.otherNotes],
  ].filter((item): item is [string, string] => Boolean(item[1]));
  if (items.length === 0) return null;
  return (
    <dl className="review-summary">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(value),
  );
}
