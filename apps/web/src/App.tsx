import { useEffect, useState } from 'react';

import type { ApiClient } from '@jobpilot/api-client';

import './styles.css';

type ConnectionStatus = 'checking' | 'connected' | 'unavailable';

interface AppProps {
  environment: string;
  healthCheck: ApiClient['getHealth'];
}

const statusLabels: Record<ConnectionStatus, string> = {
  checking: 'Checking',
  connected: 'Connected',
  unavailable: 'Unavailable',
};

export function App({ environment, healthCheck }: AppProps) {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('checking');

  useEffect(() => {
    let isCurrent = true;

    void healthCheck()
      .then(() => {
        if (isCurrent) {
          setConnectionStatus('connected');
        }
      })
      .catch(() => {
        if (isCurrent) {
          setConnectionStatus('unavailable');
        }
      });

    return () => {
      isCurrent = false;
    };
  }, [healthCheck]);

  return (
    <main className="app-shell">
      <section className="status-panel" aria-labelledby="jobpilot-title">
        <p className="phase-label">Phase 1 engineering skeleton</p>
        <h1 id="jobpilot-title">JobPilot</h1>
        <div className="status-list" aria-label="Application status">
          <p>Application: Web</p>
          <p>Environment: {environment}</p>
          <p role="status" aria-live="polite" data-status={connectionStatus}>
            API connection status: {statusLabels[connectionStatus]}
          </p>
        </div>
      </section>
    </main>
  );
}
