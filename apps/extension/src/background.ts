import { createExtensionBearerApiClient } from '@jobpilot/api-client';

import { InteractiveAuthorization } from './auth/authorization';
import { ExtensionAuthService } from './auth/auth-service';
import { loadExtensionConfig } from './auth/config';
import { refreshProviderCredentials, revokeProviderRefreshGrant } from './auth/provider-lifecycle';
import { exchangeAuthorizationCode } from './auth/provider-protocol';
import { ChromeAuthStorage } from './auth/trusted-storage';
import { createPopupMessageListener } from './background-messages';

const config = loadExtensionConfig(import.meta.env);
const storage = new ChromeAuthStorage({
  local: chrome.storage.local,
  session: chrome.storage.session,
});
const authorization = new InteractiveAuthorization({
  config: config.auth,
  store: storage,
  identity: {
    getRedirectURL: () => chrome.identity.getRedirectURL(),
    launchWebAuthFlow: (details) => chrome.identity.launchWebAuthFlow(details),
  },
});
const apiClient = createExtensionBearerApiClient({ baseUrl: config.apiBaseUrl });
const authService = new ExtensionAuthService({
  apiClient,
  authorization,
  exchangeCode: (callback) => exchangeAuthorizationCode({ callback, config: config.auth }),
  refreshCredentials: (refreshToken) =>
    refreshProviderCredentials({ config: config.auth, refreshToken }),
  revokeRefreshGrant: (refreshToken) =>
    revokeProviderRefreshGrant({ config: config.auth, refreshToken }),
  storage,
});

chrome.runtime.onMessage.addListener(
  createPopupMessageListener({
    dependencies: {
      authService,
      openWebApp: async () => {
        await chrome.tabs.create({ url: config.webAppUrl });
      },
    },
    runtime: chrome.runtime,
  }),
);
