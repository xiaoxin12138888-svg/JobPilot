import { useEffect, useState } from 'react';

import type { ApiClient, FeedbackSummary } from '@jobpilot/api-client';

import { FeedbackSummaryContent } from './FeedbackSummaryContent';

type LoadState =
  { name: 'loading' } | { name: 'error' } | { name: 'ready'; summary: FeedbackSummary };
type SettledLoad = {
  apiClient: ApiClient;
  requestNumber: number;
  state: Exclude<LoadState, { name: 'loading' }>;
};

export function FeedbackSummaryPage({ apiClient }: { apiClient: ApiClient }) {
  const [requestNumber, setRequestNumber] = useState(0);
  const [settled, setSettled] = useState<SettledLoad>();
  const state: LoadState =
    settled?.apiClient === apiClient && settled.requestNumber === requestNumber
      ? settled.state
      : { name: 'loading' };

  useEffect(() => {
    let ignore = false;
    void apiClient.getFeedbackSummary().then(
      (summary) => {
        if (!ignore) {
          setSettled({ apiClient, requestNumber, state: { name: 'ready', summary } });
        }
      },
      () => {
        if (!ignore) setSettled({ apiClient, requestNumber, state: { name: 'error' } });
      },
    );
    return () => {
      ignore = true;
    };
  }, [apiClient, requestNumber]);

  return (
    <section className="page-section feedback-page" aria-labelledby="feedback-title">
      <div className="page-heading">
        <div>
          <p className="eyebrow">LOCAL FACTS</p>
          <h1 id="feedback-title">求职复盘</h1>
          <p>基于本机投递、面试和结果记录生成的事实统计，不包含 AI 评分或建议。</p>
        </div>
      </div>
      {state.name === 'loading' && (
        <div className="loading-state" role="status" aria-live="polite">
          正在读取求职复盘…
        </div>
      )}
      {state.name === 'error' && (
        <div className="inline-error" role="alert">
          <p>求职复盘暂时无法读取。</p>
          <button
            type="button"
            className="button secondary"
            onClick={() => setRequestNumber((current) => current + 1)}
          >
            重试
          </button>
        </div>
      )}
      {state.name === 'ready' && !state.summary.hasData && (
        <div className="empty-state">
          <span aria-hidden="true">↗</span>
          <h2>还没有可复盘的求职记录</h2>
          <p>完成投递和面试记录后，这里会形成你的求职复盘。</p>
        </div>
      )}
      {state.name === 'ready' && state.summary.hasData && (
        <FeedbackSummaryContent summary={state.summary} />
      )}
    </section>
  );
}
