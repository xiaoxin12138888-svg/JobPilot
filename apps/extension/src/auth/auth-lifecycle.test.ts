import { describe, expect, it, vi } from 'vitest';

import { ApiClientError, type ExtensionBearerApiClient, type UserView } from '@jobpilot/api-client';

import { ExtensionAuthError } from './errors';
import { ExtensionAuthService } from './auth-service';
import type { ExchangedProviderCredentials } from './provider-protocol';
import { ChromeAuthStorage } from './trusted-storage';
import type {
  AccessCredential,
  RefreshGrant,
  RestoredCredentialState,
  StorageArea,
} from './trusted-storage';

const now = 1_800_000_000_000;
const oldAccessToken = 'short-lived-access-token';
const oldRefreshToken = 'old-rotating-refresh-token';
const refreshedCredentials: ExchangedProviderCredentials = {
  accessToken: 'replacement-access-token',
  accessTokenExpiresAt: now + 300_000,
  refreshToken: 'replacement-refresh-token',
};
const currentUser: UserView = {
  id: '019d4a83-cf8c-7f77-a4f0-2cc4131e3138',
  email: 'lin@example.com',
  displayName: 'Lin',
  locale: 'zh-CN',
  timeZone: 'Asia/Shanghai',
  createdAt: '2026-08-30T02:15:00Z',
  updatedAt: '2026-08-30T02:16:00Z',
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((complete, fail) => {
    resolve = complete;
    reject = fail;
  });
  return { promise, reject, resolve };
}

function memoryStorageArea(): StorageArea {
  const values: Record<string, unknown> = {};
  return {
    setAccessLevel: vi.fn(async () => undefined),
    get: vi.fn(async (key: string) => ({ [key]: values[key] })),
    set: vi.fn(async (items: Record<string, unknown>) => {
      Object.assign(values, items);
    }),
    remove: vi.fn(async (key: string) => {
      delete values[key];
    }),
  };
}

function createHarness(
  access: AccessCredential | null = {
    accessToken: oldAccessToken,
    accessTokenExpiresAt: now + 300_000,
  },
  clock: () => number = () => now,
) {
  const events: string[] = [];
  const restoreCredentials = vi.fn<() => Promise<RestoredCredentialState>>(async () => ({
    status: 'ready',
    access,
  }));
  const beginRefresh = vi.fn(async () => {
    events.push('begin-refresh');
    return { generation: 2, refreshToken: oldRefreshToken };
  });
  const saveRefreshedCredentials = vi.fn(async () => {
    events.push('save-refreshed-credentials');
  });
  const clearCredentials = vi.fn(async () => {
    events.push('clear-credentials');
  });
  const beginRevocation = vi.fn<(now: number) => Promise<RefreshGrant | null>>(async () => {
    events.push('begin-revocation');
    return { generation: 2, refreshToken: oldRefreshToken };
  });
  const clearAuthenticationState = vi.fn(async () => {
    events.push('clear-authentication-state');
  });
  const refreshCredentials = vi.fn(async () => {
    events.push('provider-refresh');
    return refreshedCredentials;
  });
  const revokeRefreshGrant = vi.fn(async () => {
    events.push('provider-revoke');
  });
  const getCurrentUser = vi.fn(async () => {
    events.push('get-current-user');
    return currentUser;
  });
  const apiClient: ExtensionBearerApiClient = {
    establishIdentity: vi.fn(async () => currentUser),
    getCurrentUser,
  };
  const service = new ExtensionAuthService({
    apiClient,
    authorization: {
      launch: vi.fn(async () => {
        throw new Error('Interactive authorization is outside this test');
      }),
    },
    clock,
    exchangeCode: vi.fn(async () => {
      throw new Error('Authorization-code exchange is outside this test');
    }),
    refreshCredentials,
    revokeRefreshGrant,
    storage: {
      beginRefresh,
      beginRevocation,
      clearAuthenticationState,
      clearCredentials,
      ensureTrustedAccess: vi.fn(async () => undefined),
      restoreCredentials,
      saveInitialCredentials: vi.fn(async () => undefined),
      saveRefreshedCredentials,
    },
  });

  return {
    beginRefresh,
    beginRevocation,
    clearAuthenticationState,
    clearCredentials,
    events,
    getCurrentUser,
    refreshCredentials,
    restoreCredentials,
    revokeRefreshGrant,
    saveRefreshedCredentials,
    service,
  };
}

describe('ExtensionAuthService access lifecycle', () => {
  it('uses an access token with more than 30 seconds remaining without refresh', async () => {
    const harness = createHarness({
      accessToken: oldAccessToken,
      accessTokenExpiresAt: now + 30_001,
    });

    await expect(harness.service.restoreCurrentUser()).resolves.toEqual(currentUser);

    expect(harness.getCurrentUser).toHaveBeenCalledWith(oldAccessToken);
    expect(harness.beginRefresh).not.toHaveBeenCalled();
    expect(harness.refreshCredentials).not.toHaveBeenCalled();
  });

  it.each([
    ['exact near-expiry boundary', now + 30_000],
    ['already expired', now - 1],
  ])('refreshes once before the API at the %s', async (_caseName, accessTokenExpiresAt) => {
    const harness = createHarness({ accessToken: oldAccessToken, accessTokenExpiresAt });

    await expect(harness.service.restoreCurrentUser()).resolves.toEqual(currentUser);

    expect(harness.events).toEqual([
      'begin-refresh',
      'provider-refresh',
      'save-refreshed-credentials',
      'get-current-user',
    ]);
    expect(harness.refreshCredentials).toHaveBeenCalledWith(oldRefreshToken);
    expect(harness.saveRefreshedCredentials).toHaveBeenCalledWith(2, refreshedCredentials, now);
    expect(harness.getCurrentUser).toHaveBeenCalledWith(refreshedCredentials.accessToken);
  });

  it('refreshes a valid refresh-only state restored after browser restart', async () => {
    const harness = createHarness(null);

    await expect(harness.service.restoreCurrentUser()).resolves.toEqual(currentUser);

    expect(harness.beginRefresh).toHaveBeenCalledOnce();
    expect(harness.getCurrentUser).toHaveBeenCalledWith(refreshedCredentials.accessToken);
  });

  it('shares one current-worker refresh across concurrent restore callers', async () => {
    const harness = createHarness(null);
    const providerResponse = deferred<ExchangedProviderCredentials>();
    harness.refreshCredentials.mockReturnValue(providerResponse.promise);

    const first = harness.service.restoreCurrentUser();
    const second = harness.service.restoreCurrentUser();
    expect(second).toBe(first);
    await vi.waitFor(() => expect(harness.refreshCredentials).toHaveBeenCalledOnce());
    providerResponse.resolve(refreshedCredentials);

    await expect(Promise.all([first, second])).resolves.toEqual([currentUser, currentUser]);
    expect(harness.beginRefresh).toHaveBeenCalledOnce();
    expect(harness.saveRefreshedCredentials).toHaveBeenCalledOnce();
    expect(harness.getCurrentUser).toHaveBeenCalledOnce();
  });

  it('lets a late restore join a refresh already claimed in real trusted storage', async () => {
    const storage = new ChromeAuthStorage({
      local: memoryStorageArea(),
      session: memoryStorageArea(),
    });
    await storage.saveInitialCredentials(
      {
        accessToken: oldAccessToken,
        accessTokenExpiresAt: now + 300_000,
        refreshToken: oldRefreshToken,
      },
      now,
    );
    const providerResponse = deferred<ExchangedProviderCredentials>();
    const refreshCredentials = vi.fn(() => providerResponse.promise);
    const getCurrentUser = vi.fn(async () => currentUser);
    const service = new ExtensionAuthService({
      apiClient: {
        establishIdentity: vi.fn(async () => currentUser),
        getCurrentUser,
      },
      authorization: {
        launch: vi.fn(async () => {
          throw new Error('Interactive authorization is outside this test');
        }),
      },
      clock: () => now + 300_000,
      exchangeCode: vi.fn(async () => {
        throw new Error('Authorization-code exchange is outside this test');
      }),
      refreshCredentials,
      revokeRefreshGrant: vi.fn(async () => undefined),
      storage,
    });

    const first = service.restoreCurrentUser();
    await vi.waitFor(() => expect(refreshCredentials).toHaveBeenCalledOnce());
    const second = service.restoreCurrentUser();
    expect(second).toBe(first);
    providerResponse.resolve({
      accessToken: refreshedCredentials.accessToken,
      accessTokenExpiresAt: now + 600_000,
      refreshToken: refreshedCredentials.refreshToken,
    });

    await expect(Promise.all([first, second])).resolves.toEqual([currentUser, currentUser]);
    expect(refreshCredentials).toHaveBeenCalledOnce();
    expect(getCurrentUser).toHaveBeenCalledOnce();
  });

  it('clears credentials after one sanitized refresh failure and never calls the API', async () => {
    const harness = createHarness(null);
    harness.refreshCredentials.mockRejectedValue(new ExtensionAuthError('AUTH_REFRESH_FAILED'));

    await expect(harness.service.restoreCurrentUser()).rejects.toEqual(
      new ExtensionAuthError('AUTH_REFRESH_FAILED'),
    );

    expect(harness.clearCredentials).toHaveBeenCalledOnce();
    expect(harness.saveRefreshedCredentials).not.toHaveBeenCalled();
    expect(harness.getCurrentUser).not.toHaveBeenCalled();
  });

  it('prioritizes unconfirmed cleanup over the refresh failure classification', async () => {
    const harness = createHarness(null);
    harness.refreshCredentials.mockRejectedValue(new ExtensionAuthError('AUTH_REFRESH_FAILED'));
    harness.clearCredentials.mockRejectedValue(new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE'));

    await expect(harness.service.restoreCurrentUser()).rejects.toEqual(
      new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE'),
    );
  });

  it('does not refresh or retry after an API 401 reached with a freshly rotated token', async () => {
    const harness = createHarness(null);
    harness.getCurrentUser.mockRejectedValue(new ApiClientError(401, 'AUTHENTICATION_REQUIRED'));

    await expect(harness.service.restoreCurrentUser()).rejects.toEqual(
      new ExtensionAuthError('AUTHENTICATION_REQUIRED'),
    );

    expect(harness.beginRefresh).toHaveBeenCalledOnce();
    expect(harness.refreshCredentials).toHaveBeenCalledOnce();
    expect(harness.getCurrentUser).toHaveBeenCalledOnce();
    expect(harness.clearCredentials).toHaveBeenCalledOnce();
  });

  it('does not let a late API 401 clear state owned by a completed logout', async () => {
    const harness = createHarness();
    const apiResponse = deferred<UserView>();
    harness.getCurrentUser.mockReturnValue(apiResponse.promise);

    const restore = harness.service.restoreCurrentUser();
    await vi.waitFor(() => expect(harness.getCurrentUser).toHaveBeenCalledOnce());
    await expect(harness.service.signOut()).resolves.toEqual({ status: 'confirmed' });
    apiResponse.reject(new ApiClientError(401, 'AUTHENTICATION_REQUIRED'));

    await expect(restore).rejects.toEqual(new ExtensionAuthError('AUTHENTICATION_REQUIRED'));
    expect(harness.clearCredentials).not.toHaveBeenCalled();
    expect(harness.clearAuthenticationState).toHaveBeenCalledOnce();
  });

  it('does not return a late successful user after a concurrent API 401 clears credentials', async () => {
    const harness = createHarness();
    const rejectedRequest = deferred<UserView>();
    harness.getCurrentUser.mockReturnValue(rejectedRequest.promise);

    const first = harness.service.restoreCurrentUser();
    const second = harness.service.restoreCurrentUser();
    expect(second).toBe(first);
    await vi.waitFor(() => expect(harness.getCurrentUser).toHaveBeenCalledOnce());
    rejectedRequest.reject(new ApiClientError(401, 'AUTHENTICATION_REQUIRED'));

    await expect(Promise.allSettled([first, second])).resolves.toEqual([
      {
        status: 'rejected',
        reason: new ExtensionAuthError('AUTHENTICATION_REQUIRED'),
      },
      {
        status: 'rejected',
        reason: new ExtensionAuthError('AUTHENTICATION_REQUIRED'),
      },
    ]);
    expect(harness.clearCredentials).toHaveBeenCalledOnce();
  });

  it('keeps a near-expiry clock change from starting refresh beside an active restore', async () => {
    const clock = vi
      .fn()
      .mockReturnValueOnce(now)
      .mockReturnValue(now + 2);
    const harness = createHarness(
      {
        accessToken: oldAccessToken,
        accessTokenExpiresAt: now + 30_001,
      },
      clock,
    );
    const apiResponse = deferred<UserView>();
    harness.getCurrentUser.mockReturnValue(apiResponse.promise);

    const first = harness.service.restoreCurrentUser();
    await vi.waitFor(() => expect(harness.getCurrentUser).toHaveBeenCalledOnce());
    const second = harness.service.restoreCurrentUser();

    expect(second).toBe(first);
    expect(harness.beginRefresh).not.toHaveBeenCalled();
    apiResponse.reject(new ApiClientError(401, 'AUTHENTICATION_REQUIRED'));
    await expect(Promise.allSettled([first, second])).resolves.toEqual([
      {
        status: 'rejected',
        reason: new ExtensionAuthError('AUTHENTICATION_REQUIRED'),
      },
      {
        status: 'rejected',
        reason: new ExtensionAuthError('AUTHENTICATION_REQUIRED'),
      },
    ]);
    expect(harness.clearCredentials).toHaveBeenCalledOnce();
  });
});

describe('ExtensionAuthService logout lifecycle', () => {
  it('reports confirmed only after provider revoke and exact local cleanup succeed', async () => {
    const harness = createHarness();

    await expect(harness.service.signOut()).resolves.toEqual({ status: 'confirmed' });

    expect(harness.events).toEqual([
      'begin-revocation',
      'provider-revoke',
      'clear-authentication-state',
    ]);
    expect(harness.revokeRefreshGrant).toHaveBeenCalledWith(oldRefreshToken);
  });

  it('reports not-applicable when no refresh grant exists and still clears all local auth state', async () => {
    const harness = createHarness();
    harness.beginRevocation.mockResolvedValue(null);

    await expect(harness.service.signOut()).resolves.toEqual({ status: 'not_applicable' });

    expect(harness.revokeRefreshGrant).not.toHaveBeenCalled();
    expect(harness.clearAuthenticationState).toHaveBeenCalledOnce();
  });

  it.each(['claim', 'provider'] as const)(
    'reports unconfirmed after a %s revoke failure and still clears local auth state',
    async (failureStage) => {
      const harness = createHarness();
      if (failureStage === 'claim') {
        harness.beginRevocation.mockRejectedValue(
          new ExtensionAuthError('AUTHENTICATION_REQUIRED'),
        );
      } else {
        harness.revokeRefreshGrant.mockRejectedValue(new ExtensionAuthError('AUTH_PROVIDER_ERROR'));
      }

      await expect(harness.service.signOut()).resolves.toEqual({ status: 'unconfirmed' });
      expect(harness.clearAuthenticationState).toHaveBeenCalledOnce();
    },
  );

  it('never returns a logout result when exact local cleanup is unconfirmed', async () => {
    const harness = createHarness();
    harness.revokeRefreshGrant.mockRejectedValue(new ExtensionAuthError('AUTH_PROVIDER_ERROR'));
    harness.clearAuthenticationState.mockRejectedValue(
      new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE'),
    );

    await expect(harness.service.signOut()).rejects.toEqual(
      new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE'),
    );
  });

  it('coalesces duplicate logout calls into one revoke and cleanup operation', async () => {
    const harness = createHarness();
    const providerResult = deferred<void>();
    harness.revokeRefreshGrant.mockReturnValue(providerResult.promise);

    const first = harness.service.signOut();
    const second = harness.service.signOut();
    await vi.waitFor(() => expect(harness.revokeRefreshGrant).toHaveBeenCalledOnce());
    providerResult.resolve();

    await expect(Promise.all([first, second])).resolves.toEqual([
      { status: 'confirmed' },
      { status: 'confirmed' },
    ]);
    expect(harness.beginRevocation).toHaveBeenCalledOnce();
    expect(harness.clearAuthenticationState).toHaveBeenCalledOnce();
  });

  it('rejects a new sign-in while logout revocation is still active', async () => {
    const harness = createHarness();
    const providerResult = deferred<void>();
    harness.revokeRefreshGrant.mockReturnValue(providerResult.promise);

    const signOut = harness.service.signOut();
    await vi.waitFor(() => expect(harness.revokeRefreshGrant).toHaveBeenCalledOnce());

    await expect(harness.service.signIn()).rejects.toEqual(
      new ExtensionAuthError('AUTHENTICATION_REQUIRED'),
    );
    providerResult.resolve();
    await expect(signOut).resolves.toEqual({ status: 'confirmed' });
  });

  it('prevents a pending refresh from resurrecting credentials after logout', async () => {
    const harness = createHarness(null);
    const providerResponse = deferred<ExchangedProviderCredentials>();
    harness.refreshCredentials.mockReturnValue(providerResponse.promise);
    harness.beginRevocation.mockRejectedValue(new ExtensionAuthError('AUTH_REFRESH_FAILED'));

    const restore = harness.service.restoreCurrentUser();
    await vi.waitFor(() => expect(harness.refreshCredentials).toHaveBeenCalledOnce());

    await expect(harness.service.signOut()).resolves.toEqual({ status: 'unconfirmed' });
    providerResponse.resolve(refreshedCredentials);
    await expect(restore).rejects.toEqual(new ExtensionAuthError('AUTHENTICATION_REQUIRED'));

    expect(harness.beginRevocation).toHaveBeenCalledOnce();
    expect(harness.clearAuthenticationState).toHaveBeenCalledOnce();
    expect(harness.saveRefreshedCredentials).not.toHaveBeenCalled();
    expect(harness.clearCredentials).not.toHaveBeenCalled();
  });
});
