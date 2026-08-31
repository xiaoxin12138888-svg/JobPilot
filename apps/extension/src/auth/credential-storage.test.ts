import { describe, expect, it, vi } from 'vitest';

import type { ExchangedProviderCredentials } from './provider-protocol';
import { ExtensionAuthError } from './errors';
import { ChromeAuthStorage, type StorageArea } from './trusted-storage';

const REFRESH_KEY = 'jobpilot.auth.refresh';
const ACCESS_KEY = 'jobpilot.auth.access';
const now = 1_800_000_000_000;
const initialCredentials: ExchangedProviderCredentials = {
  accessToken: 'initial-access-token',
  accessTokenExpiresAt: now + 300_000,
  refreshToken: 'initial-refresh-token',
};
const rotatedCredentials: ExchangedProviderCredentials = {
  accessToken: 'rotated-access-token',
  accessTokenExpiresAt: now + 360_000,
  refreshToken: 'rotated-refresh-token',
};

interface TestStorageArea extends StorageArea {
  snapshot(): Record<string, unknown>;
}

interface StorageAreaOptions {
  failSetCalls?: readonly number[];
  failRemoveCalls?: readonly number[];
}

function deferred(): { promise: Promise<void>; resolve: () => void } {
  let resolve!: () => void;
  const promise = new Promise<void>((complete) => {
    resolve = complete;
  });
  return { promise, resolve };
}

function storageArea(
  initial: Record<string, unknown> = {},
  options: StorageAreaOptions = {},
): TestStorageArea {
  const values = { ...initial };
  let setCalls = 0;
  let removeCalls = 0;
  return {
    setAccessLevel: vi.fn().mockResolvedValue(undefined),
    get: vi.fn(async (key: string) => ({ [key]: values[key] })),
    set: vi.fn(async (items: Record<string, unknown>) => {
      setCalls += 1;
      if (options.failSetCalls?.includes(setCalls)) {
        throw new Error('private storage write failed');
      }
      Object.assign(values, items);
    }),
    remove: vi.fn(async (key: string) => {
      removeCalls += 1;
      if (options.failRemoveCalls?.includes(removeCalls)) {
        throw new Error('private storage removal failed');
      }
      delete values[key];
    }),
    snapshot: () => ({ ...values }),
  };
}

function createStore(local = storageArea(), session = storageArea()) {
  return { local, session, store: new ChromeAuthStorage({ local, session }) };
}

describe('ChromeAuthStorage credential boundary', () => {
  it('commits a refresh record before access state and restores only the trusted-worker access view', async () => {
    const { local, session, store } = createStore();

    await store.saveInitialCredentials(initialCredentials, now);

    expect(vi.mocked(local.set).mock.calls).toEqual([
      [
        {
          [REFRESH_KEY]: {
            version: 1,
            status: 'ready',
            generation: 1,
            accessState: 'pending',
            refreshToken: initialCredentials.refreshToken,
          },
        },
      ],
      [
        {
          [REFRESH_KEY]: {
            version: 1,
            status: 'ready',
            generation: 1,
            accessState: 'committed',
            refreshToken: initialCredentials.refreshToken,
          },
        },
      ],
    ]);
    expect(vi.mocked(session.set).mock.calls).toEqual([
      [
        {
          [ACCESS_KEY]: {
            version: 1,
            generation: 1,
            accessToken: initialCredentials.accessToken,
            accessTokenExpiresAt: initialCredentials.accessTokenExpiresAt,
            storedAt: now,
          },
        },
      ],
    ]);
    expect(vi.mocked(local.set).mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(session.set).mock.invocationCallOrder[0] ?? Number.POSITIVE_INFINITY,
    );
    expect(vi.mocked(session.set).mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(local.set).mock.invocationCallOrder[1] ?? Number.POSITIVE_INFINITY,
    );
    expect(local.setAccessLevel).toHaveBeenCalledWith({ accessLevel: 'TRUSTED_CONTEXTS' });
    expect(session.setAccessLevel).toHaveBeenCalledWith({ accessLevel: 'TRUSTED_CONTEXTS' });
    await expect(store.restoreCredentials()).resolves.toEqual({
      status: 'ready',
      access: {
        accessToken: initialCredentials.accessToken,
        accessTokenExpiresAt: initialCredentials.accessTokenExpiresAt,
      },
    });
  });

  it('exposes an explicit trusted-storage gate for protocol calls that precede storage writes', async () => {
    const { local, session, store } = createStore();

    await store.ensureTrustedAccess();

    expect(local.setAccessLevel).toHaveBeenCalledWith({ accessLevel: 'TRUSTED_CONTEXTS' });
    expect(session.setAccessLevel).toHaveBeenCalledWith({ accessLevel: 'TRUSTED_CONTEXTS' });
    expect(local.get).not.toHaveBeenCalled();
    expect(session.get).not.toHaveBeenCalled();
    expect(local.set).not.toHaveBeenCalled();
    expect(session.set).not.toHaveBeenCalled();
  });

  it('waits for both trusted-context promises before the first credential write', async () => {
    const localGate = deferred();
    const sessionGate = deferred();
    const { local, session, store } = createStore();
    vi.mocked(local.setAccessLevel).mockReturnValue(localGate.promise);
    vi.mocked(session.setAccessLevel).mockReturnValue(sessionGate.promise);

    const savePromise = store.saveInitialCredentials(initialCredentials, now);
    await Promise.resolve();
    expect(local.set).not.toHaveBeenCalled();
    expect(session.set).not.toHaveBeenCalled();

    localGate.resolve();
    await Promise.resolve();
    expect(local.set).not.toHaveBeenCalled();
    expect(session.set).not.toHaveBeenCalled();

    sessionGate.resolve();
    await expect(savePromise).resolves.toBeUndefined();
  });

  it('restores a committed credential record after a normal service-worker restart', async () => {
    const local = storageArea();
    const session = storageArea();
    await new ChromeAuthStorage({ local, session }).saveInitialCredentials(initialCredentials, now);

    const restartedStore = new ChromeAuthStorage({ local, session });

    await expect(restartedStore.restoreCredentials()).resolves.toEqual({
      status: 'ready',
      access: {
        accessToken: initialCredentials.accessToken,
        accessTokenExpiresAt: initialCredentials.accessTokenExpiresAt,
      },
    });
  });

  it('keeps a committed rotating refresh record usable when browser restart clears session storage', async () => {
    const local = storageArea({
      [REFRESH_KEY]: {
        version: 1,
        status: 'ready',
        generation: 7,
        accessState: 'committed',
        refreshToken: 'persisted-refresh-token',
      },
    });
    const store = new ChromeAuthStorage({ local, session: storageArea() });

    await expect(store.restoreCredentials()).resolves.toEqual({ status: 'ready', access: null });
  });

  it('reports signed out when neither trusted storage area contains credentials', async () => {
    const { store } = createStore();

    await expect(store.restoreCredentials()).resolves.toEqual({ status: 'signed_out' });
  });

  it('removes the old refresh token before releasing it for one rotation request', async () => {
    const { local, session, store } = createStore();
    await store.saveInitialCredentials(initialCredentials, now);

    const grant = await store.beginRefresh(now + 301_000);

    expect(grant).toEqual({ generation: 2, refreshToken: initialCredentials.refreshToken });
    expect(local.snapshot()[REFRESH_KEY]).toEqual({
      version: 1,
      status: 'refresh_in_progress',
      generation: 2,
      startedAt: now + 301_000,
    });
    expect(JSON.stringify(local.snapshot())).not.toContain(initialCredentials.refreshToken);
    expect(session.snapshot()[ACCESS_KEY]).toBeUndefined();
    expect(vi.mocked(local.set).mock.invocationCallOrder[2]).toBeLessThan(
      vi.mocked(session.remove).mock.invocationCallOrder[0] ?? Number.POSITIVE_INFINITY,
    );
  });

  it('refuses to release a refresh token when an existing access record has another generation', async () => {
    const local = storageArea({
      [REFRESH_KEY]: {
        version: 1,
        status: 'ready',
        generation: 2,
        accessState: 'committed',
        refreshToken: 'replacement-refresh-token',
      },
    });
    const session = storageArea({
      [ACCESS_KEY]: {
        version: 1,
        generation: 1,
        accessToken: 'stale-access-token',
        accessTokenExpiresAt: now + 300_000,
        storedAt: now,
      },
    });
    const store = new ChromeAuthStorage({ local, session });

    await expect(store.beginRefresh(now + 301_000)).rejects.toEqual(
      new ExtensionAuthError('AUTHENTICATION_REQUIRED'),
    );
    expect(local.snapshot()[REFRESH_KEY]).toBeUndefined();
    expect(session.snapshot()[ACCESS_KEY]).toBeUndefined();
  });

  it('releases one old refresh token to at most one concurrent rotation caller', async () => {
    const { local, store } = createStore();
    await store.saveInitialCredentials(initialCredentials, now);

    const results = await Promise.allSettled([
      store.beginRefresh(now + 301_000),
      store.beginRefresh(now + 301_000),
    ]);

    const fulfilled = results.filter(
      (result): result is PromiseFulfilledResult<Awaited<ReturnType<typeof store.beginRefresh>>> =>
        result.status === 'fulfilled',
    );
    const rejected = results.filter(
      (result): result is PromiseRejectedResult => result.status === 'rejected',
    );
    expect(fulfilled).toHaveLength(1);
    expect(fulfilled[0]?.value).toEqual({
      generation: 2,
      refreshToken: initialCredentials.refreshToken,
    });
    expect(rejected).toHaveLength(1);
    expect(rejected[0]?.reason).toEqual(new ExtensionAuthError('AUTH_REFRESH_FAILED'));
    expect(local.snapshot()[REFRESH_KEY]).toEqual({
      version: 1,
      status: 'refresh_in_progress',
      generation: 2,
      startedAt: now + 301_000,
    });

    await store.saveRefreshedCredentials(2, rotatedCredentials, now + 302_000);
    expect(local.snapshot()[REFRESH_KEY]).toMatchObject({
      status: 'ready',
      generation: 2,
      accessState: 'committed',
      refreshToken: rotatedCredentials.refreshToken,
    });
  });

  it('commits rotated credentials only for the matching in-progress generation', async () => {
    const { local, session, store } = createStore();
    await store.saveInitialCredentials(initialCredentials, now);
    const grant = await store.beginRefresh(now + 301_000);

    await store.saveRefreshedCredentials(grant.generation, rotatedCredentials, now + 302_000);

    expect(local.snapshot()[REFRESH_KEY]).toEqual({
      version: 1,
      status: 'ready',
      generation: 2,
      accessState: 'committed',
      refreshToken: rotatedCredentials.refreshToken,
    });
    expect(session.snapshot()[ACCESS_KEY]).toEqual({
      version: 1,
      generation: 2,
      accessToken: rotatedCredentials.accessToken,
      accessTokenExpiresAt: rotatedCredentials.accessTokenExpiresAt,
      storedAt: now + 302_000,
    });
  });

  it('rejects another generation response without disturbing the active rotation', async () => {
    const { local, session, store } = createStore();
    await store.saveInitialCredentials(initialCredentials, now);
    const grant = await store.beginRefresh(now + 301_000);

    await expect(
      store.saveRefreshedCredentials(grant.generation + 1, rotatedCredentials, now + 302_000),
    ).rejects.toEqual(new ExtensionAuthError('AUTH_REFRESH_FAILED'));
    expect(local.snapshot()[REFRESH_KEY]).toEqual({
      version: 1,
      status: 'refresh_in_progress',
      generation: grant.generation,
      startedAt: now + 301_000,
    });
    expect(session.snapshot()[ACCESS_KEY]).toBeUndefined();

    await store.saveRefreshedCredentials(grant.generation, rotatedCredentials, now + 302_000);
    expect(local.snapshot()[REFRESH_KEY]).toMatchObject({
      status: 'ready',
      generation: grant.generation,
      accessState: 'committed',
    });
  });

  it.each([
    [
      'refresh in progress',
      {
        [REFRESH_KEY]: {
          version: 1,
          status: 'refresh_in_progress',
          generation: 2,
          startedAt: now,
        },
      },
      {},
    ],
    [
      'uncommitted ready record',
      {
        [REFRESH_KEY]: {
          version: 1,
          status: 'ready',
          generation: 2,
          accessState: 'pending',
          refreshToken: 'replacement-refresh-token',
        },
      },
      {},
    ],
    [
      'corrupt refresh token',
      {
        [REFRESH_KEY]: {
          version: 1,
          status: 'ready',
          generation: 1,
          accessState: 'committed',
          refreshToken: 'refresh-token\n',
        },
      },
      {},
    ],
    [
      'mismatched generations',
      {
        [REFRESH_KEY]: {
          version: 1,
          status: 'ready',
          generation: 2,
          accessState: 'committed',
          refreshToken: 'replacement-refresh-token',
        },
      },
      {
        [ACCESS_KEY]: {
          version: 1,
          generation: 1,
          accessToken: 'stale-access-token',
          accessTokenExpiresAt: now + 300_000,
          storedAt: now,
        },
      },
    ],
    [
      'orphaned access state',
      {},
      {
        [ACCESS_KEY]: {
          version: 1,
          generation: 1,
          accessToken: 'orphaned-access-token',
          accessTokenExpiresAt: now + 300_000,
          storedAt: now,
        },
      },
    ],
    [
      'unexpected refresh-record field',
      {
        [REFRESH_KEY]: {
          version: 1,
          status: 'ready',
          generation: 1,
          accessState: 'committed',
          refreshToken: 'replacement-refresh-token',
          unexpected: true,
        },
      },
      {},
    ],
  ])(
    'fails closed and clears both areas for %s after restart',
    async (_name, localData, sessionData) => {
      const local = storageArea(localData);
      const session = storageArea(sessionData);
      const store = new ChromeAuthStorage({ local, session });

      await expect(store.restoreCredentials()).rejects.toEqual(
        new ExtensionAuthError('AUTHENTICATION_REQUIRED'),
      );
      expect(local.snapshot()[REFRESH_KEY]).toBeUndefined();
      expect(session.snapshot()[ACCESS_KEY]).toBeUndefined();
    },
  );

  it.each([
    ['pending refresh write', [1], []],
    ['access write', [], [1]],
    ['ready acknowledgement', [2], []],
  ])(
    'clears every credential if the initial %s is unacknowledged',
    async (_name, localFailures, sessionFailures) => {
      const local = storageArea({}, { failSetCalls: localFailures });
      const session = storageArea({}, { failSetCalls: sessionFailures });
      const store = new ChromeAuthStorage({ local, session });

      await expect(store.saveInitialCredentials(initialCredentials, now)).rejects.toEqual(
        new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE'),
      );
      expect(local.snapshot()[REFRESH_KEY]).toBeUndefined();
      expect(session.snapshot()[ACCESS_KEY]).toBeUndefined();
    },
  );

  it('does not release a refresh token when request-start cleanup is unacknowledged', async () => {
    const local = storageArea();
    const session = storageArea({}, { failRemoveCalls: [1] });
    const store = new ChromeAuthStorage({ local, session });
    await store.saveInitialCredentials(initialCredentials, now);

    await expect(store.beginRefresh(now + 301_000)).rejects.toEqual(
      new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE'),
    );
    expect(local.snapshot()[REFRESH_KEY]).toBeUndefined();
    expect(session.snapshot()[ACCESS_KEY]).toBeUndefined();
  });

  it.each([
    ['replacement pending write', [4], []],
    ['replacement access write', [], [2]],
    ['replacement ready acknowledgement', [5], []],
  ])(
    'clears an ambiguous rotation when the %s is unacknowledged',
    async (_name, localFailures, sessionFailures) => {
      const local = storageArea({}, { failSetCalls: localFailures });
      const session = storageArea({}, { failSetCalls: sessionFailures });
      const store = new ChromeAuthStorage({ local, session });
      await store.saveInitialCredentials(initialCredentials, now);
      const grant = await store.beginRefresh(now + 301_000);

      await expect(
        store.saveRefreshedCredentials(grant.generation, rotatedCredentials, now + 302_000),
      ).rejects.toEqual(new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE'));
      expect(local.snapshot()[REFRESH_KEY]).toBeUndefined();
      expect(session.snapshot()[ACCESS_KEY]).toBeUndefined();
    },
  );

  it('fails closed before credential I/O when trusted-only access cannot be applied', async () => {
    const local = storageArea();
    const session = storageArea();
    vi.mocked(session.setAccessLevel).mockRejectedValue(new Error('private access gate failed'));
    const store = new ChromeAuthStorage({ local, session });

    await expect(store.saveInitialCredentials(initialCredentials, now)).rejects.toEqual(
      new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE'),
    );
    expect(local.set).not.toHaveBeenCalled();
    expect(session.set).not.toHaveBeenCalled();
  });

  it('clears committed access and refresh credentials together', async () => {
    const { local, session, store } = createStore();
    await store.saveInitialCredentials(initialCredentials, now);

    await store.clearCredentials();

    expect(local.snapshot()[REFRESH_KEY]).toBeUndefined();
    expect(session.snapshot()[ACCESS_KEY]).toBeUndefined();
  });

  it('reports storage unavailable when either credential cleanup cannot be confirmed', async () => {
    const local = storageArea({}, { failRemoveCalls: [1] });
    const session = storageArea();
    const store = new ChromeAuthStorage({ local, session });

    await expect(store.clearCredentials()).rejects.toEqual(
      new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE'),
    );
    expect(local.remove).toHaveBeenCalledWith(REFRESH_KEY);
    expect(session.remove).toHaveBeenCalledWith(ACCESS_KEY);
  });

  it('waits for both credential removals before reporting a cleanup failure', async () => {
    const pendingSessionRemoval = deferred();
    const local = storageArea({}, { failRemoveCalls: [1] });
    const session = storageArea();
    vi.mocked(session.remove).mockReturnValueOnce(pendingSessionRemoval.promise);
    const store = new ChromeAuthStorage({ local, session });

    const clearPromise = store.clearCredentials();
    let completed = false;
    void clearPromise.then(
      () => {
        completed = true;
      },
      () => {
        completed = true;
      },
    );
    await Promise.resolve();
    await Promise.resolve();
    expect(completed).toBe(false);

    pendingSessionRemoval.resolve();
    await expect(clearPromise).rejects.toEqual(new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE'));
  });

  it('prioritizes an unconfirmed cleanup failure over a corrupt-state classification', async () => {
    const local = storageArea(
      {
        [REFRESH_KEY]: { version: 999, refreshToken: 'must-not-survive' },
      },
      { failRemoveCalls: [1] },
    );
    const session = storageArea();
    const store = new ChromeAuthStorage({ local, session });

    await expect(store.restoreCredentials()).rejects.toEqual(
      new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE'),
    );
  });
});
