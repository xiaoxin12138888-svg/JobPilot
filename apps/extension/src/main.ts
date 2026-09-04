import { createApiClient } from '@jobpilot/api-client';

import { captureCurrentBossJob } from './capture-current-tab';
import { loadExtensionConfig } from './config';
import { initializePopup } from './popup';
import { openJobPilotJob, openManualJobForm } from './web-navigation';
import './styles.css';

const config = loadExtensionConfig({
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
});
const apiClient = createApiClient({ baseUrl: config.apiBaseUrl });

void initializePopup({
  getHealth: () => apiClient.getHealth(),
  capture: {
    captureCurrentJob: captureCurrentBossJob,
    closePopup: () => window.close(),
    createJob: (input) => apiClient.createJob(input),
    openJobPilot: (jobId) => {
      void openJobPilotJob(jobId);
    },
    openManualFallback: () => {
      void openManualJobForm();
    },
  },
});
