import { createApiClient, createExtensionBearerApiClient } from '@jobpilot/api-client';

const baseUrl = import.meta.env.VITE_API_BASE_URL;

export const apiClient = createApiClient({
  baseUrl,
});

export const extensionBearerApiClient = createExtensionBearerApiClient({
  baseUrl,
});
