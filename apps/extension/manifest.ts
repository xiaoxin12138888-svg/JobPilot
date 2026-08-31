import type { ExtensionConfig } from './src/auth/config.ts';

export function createManifest(config: ExtensionConfig): chrome.runtime.ManifestV3 {
  const hostPermissions = [
    `${new URL(config.apiBaseUrl).origin}/*`,
    `${new URL(config.auth.issuer).origin}/*`,
  ];

  return {
    manifest_version: 3,
    name: 'JobPilot Extension',
    description: 'Securely connect the JobPilot browser extension to your JobPilot account',
    version: '0.1.0',
    minimum_chrome_version: '106',
    action: {
      default_popup: 'popup.html',
      default_title: 'Open JobPilot Extension',
    },
    background: {
      service_worker: 'background.js',
      type: 'module',
    },
    permissions: ['identity', 'storage'],
    host_permissions: [...new Set(hostPermissions)],
    content_security_policy: {
      extension_pages: "script-src 'self'; object-src 'self'",
    },
  };
}
