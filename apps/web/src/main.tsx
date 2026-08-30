import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './App';
import { apiClient } from './api';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('JobPilot Web root element was not found');
}

createRoot(rootElement).render(
  <StrictMode>
    <App environment={import.meta.env.MODE} healthCheck={apiClient.getHealth} />
  </StrictMode>,
);
