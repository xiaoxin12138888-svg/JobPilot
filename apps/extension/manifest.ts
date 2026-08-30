import { validateApiBaseUrl } from '@jobpilot/api-client';

export function createManifest(apiBaseUrl: string): chrome.runtime.ManifestV3 {
  const parsedApiUrl = validateApiBaseUrl(apiBaseUrl);

  return {
    manifest_version: 3,
    name: 'JobPilot Extension',
    description: 'JobPilot Phase 1 engineering skeleton',
    version: '0.1.0',
    action: {
      default_popup: 'popup.html',
      default_title: 'Open JobPilot Extension',
    },
    permissions: ['activeTab'],
    host_permissions: [`${parsedApiUrl.origin}/*`],
  };
}
