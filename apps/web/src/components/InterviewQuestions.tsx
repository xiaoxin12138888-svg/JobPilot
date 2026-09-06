import { useState } from 'react';

import { QUESTION_CATEGORY_LABELS, QUESTION_PERFORMANCE_LABELS } from '@jobpilot/api-client';
import type {
  ApiClient,
  CreateInterviewQuestionInput,
  InterviewQuestion,
} from '@jobpilot/api-client';

import { InterviewQuestionForm } from './InterviewQuestionForm';

export function InterviewQuestions({
  apiClient,
  interviewId,
  questions,
  onChange,
}: {
  apiClient: ApiClient;
  interviewId: string;
  questions: InterviewQuestion[];
  onChange(questions: InterviewQuestion[]): void;
}) {
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<string>();
  const [error, setError] = useState<string>();

  async function create(input: CreateInterviewQuestionInput) {
    setError(undefined);
    try {
      const created = await apiClient.createInterviewQuestion(interviewId, input);
      onChange([...questions, created]);
      setCreating(false);
    } catch {
      setError('面试题保存失败，请稍后重试。');
    }
  }

  async function update(questionId: string, input: CreateInterviewQuestionInput) {
    setError(undefined);
    try {
      const updated = await apiClient.updateInterviewQuestion(questionId, input);
      onChange(questions.map((item) => (item.id === questionId ? updated : item)));
      setEditingId(undefined);
    } catch {
      setError('面试题更新失败，请稍后重试。');
    }
  }

  async function remove(questionId: string) {
    if (!window.confirm('删除这道面试题？')) return;
    setError(undefined);
    try {
      await apiClient.deleteInterviewQuestion(questionId);
      onChange(questions.filter((item) => item.id !== questionId));
    } catch {
      setError('面试题删除失败，请稍后重试。');
    }
  }

  return (
    <section className="question-section" aria-label="面试问题">
      <div className="question-section-heading">
        <h4>面试问题</h4>
        {!creating && (
          <button type="button" className="text-button" onClick={() => setCreating(true)}>
            添加问题
          </button>
        )}
      </div>
      {creating && (
        <InterviewQuestionForm
          submitLabel="保存题目"
          onCancel={() => setCreating(false)}
          onSubmit={create}
        />
      )}
      {questions.length === 0 && !creating ? (
        <p className="muted">还没有记录题目</p>
      ) : (
        <div className="question-list">
          {questions.map((question) =>
            editingId === question.id ? (
              <InterviewQuestionForm
                key={question.id}
                initial={question}
                submitLabel="保存题目修改"
                onCancel={() => setEditingId(undefined)}
                onSubmit={(input) => update(question.id, input)}
              />
            ) : (
              <article className="question-card" key={question.id}>
                <div className="question-card-heading">
                  <h5>{question.question}</h5>
                  <div className="compact-actions">
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => setEditingId(question.id)}
                    >
                      编辑题目
                    </button>
                    <button
                      type="button"
                      className="text-button danger-text"
                      onClick={() => void remove(question.id)}
                    >
                      删除题目
                    </button>
                  </div>
                </div>
                <p className="question-meta">
                  <span>{QUESTION_CATEGORY_LABELS[question.category]}</span>
                  <span>{QUESTION_PERFORMANCE_LABELS[question.performance]}</span>
                </p>
                {question.answerSummary && (
                  <div className="question-copy">
                    <strong>我的回答</strong>
                    <p>{question.answerSummary}</p>
                  </div>
                )}
                {question.note && (
                  <div className="question-copy">
                    <strong>备注</strong>
                    <p>{question.note}</p>
                  </div>
                )}
              </article>
            ),
          )}
        </div>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
