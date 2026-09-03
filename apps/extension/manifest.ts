import type { ExtensionConfig } from './src/config.ts';

export function createManifest(config: ExtensionConfig): chrome.runtime.ManifestV3 {
  return {
    manifest_version: 3,
    name: 'JobPilot Extension',
    description: 'Capture the current BOSS job into the local JobPilot workspace',
    version: '0.1.0',
    minimum_chrome_version: '106',
    action: {
      default_popup: 'popup.html',
      default_title: 'Capture current BOSS job',
    },
    permissions: ['activeTab', 'scripting'],
    host_permissions: [`${config.apiBaseUrl}/*`],
    content_security_policy: {
      extension_pages:
        `default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; ` +
        `connect-src ${config.apiBaseUrl}; base-uri 'none'`,
    },
  };
}
