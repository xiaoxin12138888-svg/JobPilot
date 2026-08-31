import { useEffect, useState } from 'react';

import type { ApiClient } from '@jobpilot/api-client';

import './styles.css';

type HealthClient = Pick<ApiClient, 'getHealth'>;
type LocalApiStatus = 'checking' | 'ready' | 'unavailable';
type SettledHealthRequest = {
  apiClient: HealthClient;
  requestNumber: number;
  status: Exclude<LocalApiStatus, 'checking'>;
};

interface AppProps {
  apiClient: HealthClient;
}

export function App({ apiClient }: AppProps) {
  const { status, retry } = useLocalApiHealth(apiClient);

  return (
    <main className="app-shell">
      <section className="status-panel" aria-labelledby="jobpilot-title">
        <header className="brand-header">
          <p className="product-label">本地个人求职工作台</p>
          <h1 id="jobpilot-title">JobPilot</h1>
        </header>

        {status === 'checking' && (
          <div className="service-state" role="status" aria-live="polite" aria-busy="true">
            <h2>正在连接本地服务…</h2>
            <p>正在检查本机 JobPilot API。</p>
          </div>
        )}

        {status === 'ready' && (
          <div className="service-state" role="status" aria-live="polite">
            <h2>本地服务已就绪</h2>
            <p>JobPilot 已连接到本机 API。</p>
          </div>
        )}

        {status === 'unavailable' && (
          <div className="service-state error-state" role="alert">
            <h2>无法连接本地服务</h2>
            <p>请确认本机 JobPilot API 已启动，然后重试。</p>
            <button type="button" className="retry-action" onClick={retry}>
              重试
            </button>
          </div>
        )}
      </section>
    </main>
  );
}

function useLocalApiHealth(apiClient: HealthClient): {
  status: LocalApiStatus;
  retry(): void;
} {
  const [requestNumber, setRequestNumber] = useState(0);
  const [settledRequest, setSettledRequest] = useState<SettledHealthRequest>();
  const status =
    settledRequest?.apiClient === apiClient && settledRequest.requestNumber === requestNumber
      ? settledRequest.status
      : 'checking';

  useEffect(() => {
    let ignoreResult = false;

    void apiClient.getHealth().then(
      () => {
        if (!ignoreResult) {
          setSettledRequest({ apiClient, requestNumber, status: 'ready' });
        }
      },
      () => {
        if (!ignoreResult) {
          setSettledRequest({ apiClient, requestNumber, status: 'unavailable' });
        }
      },
    );

    return () => {
      ignoreResult = true;
    };
  }, [apiClient, requestNumber]);

  return {
    status,
    retry: () => {
      setRequestNumber((current) => current + 1);
    },
  };
}
