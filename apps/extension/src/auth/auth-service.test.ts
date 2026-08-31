import { describe, expect, it, vi } from 'vitest';

import { ApiClientError, type ExtensionBearerApiClient, type UserView } from '@jobpilot/api-client';

import type { ValidatedAuthorizationCallback } from './authorization';
import { ExtensionAuthError } from './errors';
import { ExtensionAuthService } from './auth-service';
import type { ExchangedProviderCredentials } from './provider-protocol';
import type { RestoredCredentialState } from './trusted-storage';

const now = 1_800_000_000_000;
const credentials: ExchangedProviderCredentials = {
  accessToken: 'short-lived-access-token',
  accessTokenExpiresAt: now + 300_000,
  refreshToken: 'rotating-refresh-token',
};
const establishedUser: UserView = {
  id: '019d4a83-cf8c-7f77-a4f0-2cc4131e3138',
  email: 'lin@example.com',
  displayName: null,
  locale: null,
  timeZone: null,
  createdAt: '2026-08-30T02:15:00Z',
  updatedAt: '2026-08-30T02:15:00Z',
};
const currentUser: UserView = {
  ...establishedUser,
  displayName: 'Lin',
  locale: 'zh-CN',
  timeZone: 'Asia/Shanghai',
  updatedAt: '2026-08-30T02:16:00Z',
};
const callback = {
  parameters: new URLSearchParams('code=authorization-code'),
  attempt: {
    version: 1,
    state: 's'.repeat(43),
    nonce: 'n'.repeat(43),
    codeVerifier: 'v'.repeat(64),
    redirectUri: 'https://abcdefghijklmnopabcdefghijklmnop.chromiumapp.org/',
    createdAt: now - 1_000,
    expiresAt: now + 599_000,
  },
} satisfies ValidatedAuthorizationCallback;

function createHarness() {
  const events: string[] = [];
  const ensureTrustedAccess = vi.fn(async () => {
    events.push('trusted-access');
  });
  const saveInitialCredentials = vi.fn(async () => {
    events.push('save-credentials');
  });
  const restoreCredentials = vi
    .fn<() => Promise<RestoredCredentialState>>()
    .mockResolvedValue({ status: 'signed_out' });
  const clearCredentials = vi.fn(async () => {
    events.push('clear-credentials');
  });
  const launch = vi.fn(async () => {
    events.push('launch');
    return callback;
  });
  const exchangeCode = vi.fn(async () => {
    events.push('exchange');
    return credentials;
  });
  const establishIdentity = vi.fn(async () => {
    events.push('establish-identity');
    return establishedUser;
  });
  const getCurrentUser = vi.fn(async () => {
    events.push('get-current-user');
    return currentUser;
  });
  const apiClient: ExtensionBearerApiClient = {
    establishIdentity,
    getCurrentUser,
  };
  const service = new ExtensionAuthService({
    apiClient,
    authorization: { launch },
    clock: () => now,
    exchangeCode,
    storage: {
      ensureTrustedAccess,
      saveInitialCredentials,
      restoreCredentials,
      clearCredentials,
    },
  });

  return {
    apiClient,
    clearCredentials,
    ensureTrustedAccess,
    events,
    exchangeCode,
    getCurrentUser,
    launch,
    restoreCredentials,
    saveInitialCredentials,
    service,
    establishIdentity,
  };
}

describe('ExtensionAuthService', () => {
  it('signs in through the strict trusted protocol and API establishment order', async () => {
    const harness = createHarness();

    const result = await harness.service.signIn();

    expect(result).toEqual(currentUser);
    expect(harness.events).toEqual([
      'trusted-access',
      'launch',
      'exchange',
      'save-credentials',
      'establish-identity',
      'get-current-user',
    ]);
    expect(harness.exchangeCode).toHaveBeenCalledWith(callback);
    expect(harness.saveInitialCredentials).toHaveBeenCalledWith(credentials, now);
    expect(harness.establishIdentity).toHaveBeenCalledWith(credentials.accessToken);
    expect(harness.getCurrentUser).toHaveBeenCalledWith(credentials.accessToken);
    expect(JSON.stringify(result)).not.toContain(credentials.refreshToken);
  });

  it('performs no protocol or API work when the trusted-storage gate fails', async () => {
    const harness = createHarness();
    harness.ensureTrustedAccess.mockRejectedValue(
      new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE'),
    );

    await expect(harness.service.signIn()).rejects.toEqual(
      new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE'),
    );
    expect(harness.launch).not.toHaveBeenCalled();
    expect(harness.exchangeCode).not.toHaveBeenCalled();
    expect(harness.saveInitialCredentials).not.toHaveBeenCalled();
    expect(harness.establishIdentity).not.toHaveBeenCalled();
    expect(harness.getCurrentUser).not.toHaveBeenCalled();
  });

  it.each(['launch', 'exchange', 'save'] as const)(
    'stops before the API when %s fails',
    async (failureStage) => {
      const harness = createHarness();
      const failure = new ExtensionAuthError('AUTH_TOKEN_EXCHANGE_FAILED');
      if (failureStage === 'launch') {
        harness.launch.mockRejectedValue(failure);
      } else if (failureStage === 'exchange') {
        harness.exchangeCode.mockRejectedValue(failure);
      } else {
        harness.saveInitialCredentials.mockRejectedValue(failure);
      }

      await expect(harness.service.signIn()).rejects.toBe(failure);
      expect(harness.establishIdentity).not.toHaveBeenCalled();
      expect(harness.getCurrentUser).not.toHaveBeenCalled();
    },
  );

  it('clears credentials for any establishment 401 without retrying or reading me', async () => {
    const harness = createHarness();
    harness.establishIdentity.mockRejectedValue(new ApiClientError(401, 'UNEXPECTED_API_ERROR'));

    await expect(harness.service.signIn()).rejects.toEqual(
      new ExtensionAuthError('AUTHENTICATION_REQUIRED'),
    );
    expect(harness.establishIdentity).toHaveBeenCalledOnce();
    expect(harness.getCurrentUser).not.toHaveBeenCalled();
    expect(harness.clearCredentials).toHaveBeenCalledOnce();
  });

  it('clears credentials for a current-user 401 without refreshing or retrying', async () => {
    const harness = createHarness();
    harness.getCurrentUser.mockRejectedValue(new ApiClientError(401, 'AUTHENTICATION_REQUIRED'));

    await expect(harness.service.signIn()).rejects.toEqual(
      new ExtensionAuthError('AUTHENTICATION_REQUIRED'),
    );
    expect(harness.establishIdentity).toHaveBeenCalledOnce();
    expect(harness.getCurrentUser).toHaveBeenCalledOnce();
    expect(harness.clearCredentials).toHaveBeenCalledOnce();
  });

  it('prioritizes an unconfirmed credential cleanup over the API 401 classification', async () => {
    const harness = createHarness();
    harness.getCurrentUser.mockRejectedValue(new ApiClientError(401, 'AUTHENTICATION_REQUIRED'));
    harness.clearCredentials.mockRejectedValue(new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE'));

    await expect(harness.service.signIn()).rejects.toEqual(
      new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE'),
    );
  });

  it('preserves a sanitized non-401 API failure without clearing or retrying', async () => {
    const harness = createHarness();
    const unavailable = new ApiClientError(503, 'DEPENDENCY_UNAVAILABLE');
    harness.getCurrentUser.mockRejectedValue(unavailable);

    await expect(harness.service.signIn()).rejects.toBe(unavailable);
    expect(harness.getCurrentUser).toHaveBeenCalledOnce();
    expect(harness.clearCredentials).not.toHaveBeenCalled();
  });

  it('returns signed out without calling OAuth or the API when no credentials exist', async () => {
    const harness = createHarness();

    await expect(harness.service.restoreCurrentUser()).resolves.toBeNull();
    expect(harness.launch).not.toHaveBeenCalled();
    expect(harness.exchangeCode).not.toHaveBeenCalled();
    expect(harness.establishIdentity).not.toHaveBeenCalled();
    expect(harness.getCurrentUser).not.toHaveBeenCalled();
  });

  it('restores an existing user directly through me without provisioning again', async () => {
    const harness = createHarness();
    harness.restoreCredentials.mockResolvedValue({
      status: 'ready',
      access: {
        accessToken: credentials.accessToken,
        accessTokenExpiresAt: credentials.accessTokenExpiresAt,
      },
    });

    await expect(harness.service.restoreCurrentUser()).resolves.toEqual(currentUser);
    expect(harness.getCurrentUser).toHaveBeenCalledWith(credentials.accessToken);
    expect(harness.establishIdentity).not.toHaveBeenCalled();
    expect(harness.launch).not.toHaveBeenCalled();
    expect(harness.exchangeCode).not.toHaveBeenCalled();
    expect(harness.saveInitialCredentials).not.toHaveBeenCalled();
  });

  it('clears a restored credential after one current-user 401', async () => {
    const harness = createHarness();
    harness.restoreCredentials.mockResolvedValue({
      status: 'ready',
      access: {
        accessToken: credentials.accessToken,
        accessTokenExpiresAt: credentials.accessTokenExpiresAt,
      },
    });
    harness.getCurrentUser.mockRejectedValue(new ApiClientError(401, 'UNEXPECTED_API_ERROR'));

    await expect(harness.service.restoreCurrentUser()).rejects.toEqual(
      new ExtensionAuthError('AUTHENTICATION_REQUIRED'),
    );
    expect(harness.getCurrentUser).toHaveBeenCalledOnce();
    expect(harness.clearCredentials).toHaveBeenCalledOnce();
  });

  it('keeps a valid refresh-only restart state for Task 7F without making an API call', async () => {
    const harness = createHarness();
    harness.restoreCredentials.mockResolvedValue({ status: 'ready', access: null });

    await expect(harness.service.restoreCurrentUser()).rejects.toEqual(
      new ExtensionAuthError('AUTHENTICATION_REQUIRED'),
    );
    expect(harness.getCurrentUser).not.toHaveBeenCalled();
    expect(harness.clearCredentials).not.toHaveBeenCalled();
  });
});
