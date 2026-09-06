import { useState } from 'react';

import { INTERVIEW_TYPE_LABELS } from '@jobpilot/api-client';
import type {
  CreateInterviewRoundInput,
  InterviewRound,
  InterviewType,
} from '@jobpilot/api-client';

export function InterviewRoundForm({
  initial,
  submitLabel,
  onCancel,
  onSubmit,
}: {
  initial?: InterviewRound;
  submitLabel: string;
  onCancel(): void;
  onSubmit(input: CreateInterviewRoundInput): Promise<void>;
}) {
  const [roundName, setRoundName] = useState(initial?.roundName ?? '');
  const [interviewType, setInterviewType] = useState<InterviewType>(
    initial?.interviewType ?? 'VIDEO',
  );
  const [scheduledAt, setScheduledAt] = useState(toLocalDateTime(initial?.scheduledAt));
  const [interviewerNote, setInterviewerNote] = useState(initial?.interviewerNote ?? '');
  const [wentWell, setWentWell] = useState(initial?.wentWell ?? '');
  const [couldImprove, setCouldImprove] = useState(initial?.couldImprove ?? '');
  const [learningNotes, setLearningNotes] = useState(initial?.learningNotes ?? '');
  const [otherNotes, setOtherNotes] = useState(initial?.otherNotes ?? '');
  const [saving, setSaving] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!roundName.trim()) return;
    setSaving(true);
    await onSubmit({
      roundName: roundName.trim(),
      interviewType,
      scheduledAt: scheduledAt ? new Date(scheduledAt).toISOString() : null,
      interviewerNote: optionalText(interviewerNote),
      ...(initial
        ? {
            wentWell: optionalText(wentWell),
            couldImprove: optionalText(couldImprove),
            learningNotes: optionalText(learningNotes),
            otherNotes: optionalText(otherNotes),
          }
        : {}),
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
      <TextField label="面试官备注" value={interviewerNote} onChange={setInterviewerNote} />
      {initial && (
        <>
          <TextField label="做得好的地方" value={wentWell} onChange={setWentWell} />
          <TextField label="没答好的地方" value={couldImprove} onChange={setCouldImprove} />
          <TextField label="需要补充学习" value={learningNotes} onChange={setLearningNotes} />
          <TextField label="其他备注" value={otherNotes} onChange={setOtherNotes} />
        </>
      )}
      <div className="form-actions interview-form-wide">
        <button type="button" className="button secondary" onClick={onCancel}>
          取消
        </button>
        <button type="submit" className="button primary" disabled={saving || !roundName.trim()}>
          {saving ? '正在保存…' : submitLabel}
        </button>
      </div>
    </form>
  );
}

function TextField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange(value: string): void;
}) {
  return (
    <label className="field interview-form-wide">
      <span>{label}</span>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function optionalText(value: string): string | null {
  return value.trim() || null;
}

function toLocalDateTime(value: string | null | undefined): string {
  if (!value) return '';
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}
