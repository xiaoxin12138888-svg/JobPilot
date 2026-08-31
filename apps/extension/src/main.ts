import { createApiClient } from '@jobpilot/api-client';

import { loadExtensionConfig } from './config';
import { initializePopup } from './popup';
import './styles.css';

const config = loadExtensionConfig({
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
});
const apiClient = createApiClient({ baseUrl: config.apiBaseUrl });

void initializePopup({
  getHealth: () => apiClient.getHealth(),
});
