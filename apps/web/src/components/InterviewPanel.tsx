import { useEffect, useState } from 'react';

import type {
  ApiClient,
  Application,
  CreateInterviewRoundInput,
  InterviewRound,
} from '@jobpilot/api-client';

import { InterviewRoundCard } from './InterviewRoundCard';
import { InterviewRoundForm } from './InterviewRoundForm';

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
            <InterviewRoundForm
              submitLabel="保存面试"
              onCancel={() => setCreating(false)}
              onSubmit={createInterview}
            />
          )}
          {interviews.length > 0 && (
            <div className="interview-list">
              {interviews.map((interview) => (
                <InterviewRoundCard
                  key={interview.id}
                  apiClient={apiClient}
                  interview={interview}
                  onUpdate={(updated) =>
                    setInterviews((current) =>
                      current.map((item) => (item.id === updated.id ? updated : item)),
                    )
                  }
                  onDelete={(interviewId) =>
                    setInterviews((current) => current.filter((item) => item.id !== interviewId))
                  }
                />
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
