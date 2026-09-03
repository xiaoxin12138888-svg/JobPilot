import { useEffect, useState } from 'react';

import type { ApiClient, Job } from '@jobpilot/api-client';

import { JobDetail } from './components/JobDetail';
import { JobForm } from './components/JobForm';
import { JobLibrary } from './components/JobLibrary';
import './styles.css';

type LocalApiStatus = 'checking' | 'ready' | 'unavailable';
type SettledHealthRequest = {
  apiClient: ApiClient;
  requestNumber: number;
  status: Exclude<LocalApiStatus, 'checking'>;
};
type View = { name: 'library' } | { name: 'create' } | { name: 'detail'; jobId: string };

interface AppProps {
  apiClient: ApiClient;
}

export function App({ apiClient }: AppProps) {
  const { status, retry } = useLocalApiHealth(apiClient);

  if (status !== 'ready') {
    return <ServiceState status={status} retry={retry} />;
  }
  return <Workspace apiClient={apiClient} />;
}

function Workspace({ apiClient }: AppProps) {
  const [view, setView] = useState<View>(initialViewFromLocation);

  function navigate(nextView: View) {
    setView(nextView);
    const query =
      nextView.name === 'detail'
        ? `?jobId=${encodeURIComponent(nextView.jobId)}`
        : nextView.name === 'create'
          ? '?view=create'
          : '';
    window.history.replaceState(null, '', `${window.location.pathname}${query}`);
  }

  if (view.name === 'create') {
    return (
      <AppFrame>
        <JobForm
          onCancel={() => navigate({ name: 'library' })}
          onSubmit={async (input) => {
            const job = await apiClient.createJob(input);
            navigate({ name: 'detail', jobId: job.id });
          }}
        />
      </AppFrame>
    );
  }
  if (view.name === 'detail') {
    return (
      <AppFrame>
        <JobDetail
          apiClient={apiClient}
          jobId={view.jobId}
          onBack={() => navigate({ name: 'library' })}
          onDeleted={() => navigate({ name: 'library' })}
        />
      </AppFrame>
    );
  }
  return (
    <AppFrame>
      <JobLibrary
        apiClient={apiClient}
        onAdd={() => navigate({ name: 'create' })}
        onOpen={(job: Job) => navigate({ name: 'detail', jobId: job.id })}
      />
    </AppFrame>
  );
}

function initialViewFromLocation(): View {
  const params = new URLSearchParams(window.location.search);
  const jobId = params.get('jobId')?.trim();
  if (jobId && jobId.length <= 36) return { name: 'detail', jobId };
  if (params.get('view') === 'create') return { name: 'create' };
  return { name: 'library' };
}

function AppFrame({ children }: { children: React.ReactNode }) {
  return (
    <main className="workspace-shell">
      <header className="topbar">
        <div>
          <p className="product-label">本地个人求职工作台</p>
          <p className="wordmark">JobPilot</p>
        </div>
        <span className="local-badge">仅保存在本机</span>
      </header>
      {children}
    </main>
  );
}

function ServiceState({
  status,
  retry,
}: {
  status: Exclude<LocalApiStatus, 'ready'>;
  retry(): void;
}) {
  return (
    <main className="service-shell">
      <section className="status-panel" aria-labelledby="jobpilot-title">
        <header className="brand-header">
          <p className="product-label">本地个人求职工作台</p>
          <h1 id="jobpilot-title">JobPilot</h1>
        </header>
        {status === 'checking' ? (
          <div className="service-state" role="status" aria-live="polite" aria-busy="true">
            <h2>正在连接本地服务…</h2>
            <p>正在检查本机 JobPilot API。</p>
          </div>
        ) : (
          <div className="service-state error-state" role="alert">
            <h2>无法连接本地服务</h2>
            <p>请确认本机 JobPilot API 已启动，然后重试。</p>
            <button type="button" className="button secondary" onClick={retry}>
              重试
            </button>
          </div>
        )}
      </section>
    </main>
  );
}

function useLocalApiHealth(apiClient: ApiClient): {
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
        if (!ignoreResult) setSettledRequest({ apiClient, requestNumber, status: 'ready' });
      },
      () => {
        if (!ignoreResult) setSettledRequest({ apiClient, requestNumber, status: 'unavailable' });
      },
    );
    return () => {
      ignoreResult = true;
    };
  }, [apiClient, requestNumber]);

  return { status, retry: () => setRequestNumber((current) => current + 1) };
}
