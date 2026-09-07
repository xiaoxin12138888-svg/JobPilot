import { createApiClient } from '@jobpilot/api-client';

import { captureCurrentJob } from './capture-current-tab';
import { loadExtensionConfig } from './config';
import { fillCurrentApplicationForm } from './fill-current-tab';
import { initializePopup } from './popup';
import { scanCurrentApplicationForm } from './scan-current-tab';
import { openAutofillProfile, openJobPilotJob, openManualJobForm } from './web-navigation';
import './styles.css';

const config = loadExtensionConfig({
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
});
const apiClient = createApiClient({ baseUrl: config.apiBaseUrl });

void initializePopup({
  getHealth: () => apiClient.getHealth(),
  autofill: {
    closePopup: () => window.close(),
    fillCurrentForm: fillCurrentApplicationForm,
    getAutofillProfile: () => apiClient.getAutofillProfile(),
    openProfile: () => {
      void openAutofillProfile();
    },
    scanCurrentForm: scanCurrentApplicationForm,
  },
  capture: {
    captureCurrentJob,
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
