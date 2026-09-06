import { useState } from 'react';

import { QUESTION_CATEGORY_LABELS, QUESTION_PERFORMANCE_LABELS } from '@jobpilot/api-client';
import type {
  CreateInterviewQuestionInput,
  InterviewQuestion,
  QuestionCategory,
  QuestionPerformance,
} from '@jobpilot/api-client';

export function InterviewQuestionForm({
  initial,
  submitLabel,
  onCancel,
  onSubmit,
}: {
  initial?: InterviewQuestion;
  submitLabel: string;
  onCancel(): void;
  onSubmit(input: CreateInterviewQuestionInput): Promise<void>;
}) {
  const [question, setQuestion] = useState(initial?.question ?? '');
  const [category, setCategory] = useState<QuestionCategory>(initial?.category ?? 'OTHER');
  const [answerSummary, setAnswerSummary] = useState(initial?.answerSummary ?? '');
  const [performance, setPerformance] = useState<QuestionPerformance>(
    initial?.performance ?? 'NOT_SURE',
  );
  const [note, setNote] = useState(initial?.note ?? '');
  const [saving, setSaving] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    setSaving(true);
    await onSubmit({
      question: question.trim(),
      category,
      answerSummary: answerSummary.trim() || null,
      performance,
      note: note.trim() || null,
    });
    setSaving(false);
  }

  return (
    <form className="question-form" onSubmit={(event) => void submit(event)}>
      <label className="field question-form-wide">
        <span>问题 *</span>
        <textarea required value={question} onChange={(event) => setQuestion(event.target.value)} />
      </label>
      <label className="field">
        <span>分类</span>
        <select
          value={category}
          onChange={(event) => setCategory(event.target.value as QuestionCategory)}
        >
          {Object.entries(QUESTION_CATEGORY_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>表现</span>
        <select
          value={performance}
          onChange={(event) => setPerformance(event.target.value as QuestionPerformance)}
        >
          {Object.entries(QUESTION_PERFORMANCE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label className="field question-form-wide">
        <span>我的回答</span>
        <textarea
          value={answerSummary}
          onChange={(event) => setAnswerSummary(event.target.value)}
        />
      </label>
      <label className="field question-form-wide">
        <span>题目备注</span>
        <textarea value={note} onChange={(event) => setNote(event.target.value)} />
      </label>
      <div className="form-actions question-form-wide">
        <button type="button" className="button secondary" onClick={onCancel}>
          取消
        </button>
        <button type="submit" className="button primary" disabled={saving || !question.trim()}>
          {saving ? '正在保存…' : submitLabel}
        </button>
      </div>
    </form>
  );
}
