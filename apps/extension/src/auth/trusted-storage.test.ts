import { describe, expect, it, vi } from 'vitest';

import { ExtensionAuthError } from './errors';
import type { AuthorizationAttempt } from './authorization';
import { ChromeAuthStorage, type StorageArea } from './trusted-storage';

const extensionId = 'abcdefghijklmnopabcdefghijklmnop';
const validAttempt: AuthorizationAttempt = {
  version: 1,
  state: 's'.repeat(43),
  nonce: 'n'.repeat(43),
  codeVerifier: 'a'.repeat(64),
  redirectUri: `https://${extensionId}.chromiumapp.org/`,
  createdAt: 1_800_000_000_000,
  expiresAt: 1_800_000_600_000,
};

function storageArea(initial: Record<string, unknown> = {}): StorageArea {
  const values = { ...initial };
  return {
    setAccessLevel: vi.fn().mockResolvedValue(undefined),
    get: vi.fn(async (key: string) => ({ [key]: values[key] })),
    set: vi.fn(async (items: Record<string, unknown>) => {
      Object.assign(values, items);
    }),
    remove: vi.fn(async (key: string) => {
      delete values[key];
    }),
  };
}

describe('ChromeAuthStorage attempt boundary', () => {
  it('awaits trusted-only access for both areas before storing or reading an attempt', async () => {
    const local = storageArea();
    const session = storageArea();
    const store = new ChromeAuthStorage({ local, session });

    await store.saveAttempt(validAttempt);
    await expect(store.loadAttempt()).resolves.toEqual(validAttempt);

    expect(local.setAccessLevel).toHaveBeenCalledWith({ accessLevel: 'TRUSTED_CONTEXTS' });
    expect(session.setAccessLevel).toHaveBeenCalledWith({ accessLevel: 'TRUSTED_CONTEXTS' });
    expect(vi.mocked(local.setAccessLevel).mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(session.set).mock.invocationCallOrder[0] ?? Number.POSITIVE_INFINITY,
    );
    expect(vi.mocked(session.setAccessLevel).mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(session.set).mock.invocationCallOrder[0] ?? Number.POSITIVE_INFINITY,
    );
  });

  it('fails closed without writing when trusted-only access cannot be applied', async () => {
    const local = storageArea();
    const session = storageArea();
    vi.mocked(local.setAccessLevel).mockRejectedValue(new Error('private storage error'));
    const store = new ChromeAuthStorage({ local, session });

    await expect(store.saveAttempt(validAttempt)).rejects.toEqual(
      new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE'),
    );
    expect(session.set).not.toHaveBeenCalled();
  });

  it.each(['load', 'clear'] as const)(
    'awaits both trusted-only access gates before a first %s operation',
    async (operation) => {
      const local = storageArea();
      const session = storageArea({ 'jobpilot.auth.attempt': validAttempt });
      const store = new ChromeAuthStorage({ local, session });

      if (operation === 'load') {
        await store.loadAttempt();
      } else {
        await store.clearAttempt();
      }

      const storageCall = operation === 'load' ? session.get : session.remove;
      expect(vi.mocked(local.setAccessLevel).mock.invocationCallOrder[0]).toBeLessThan(
        vi.mocked(storageCall).mock.invocationCallOrder[0] ?? Number.POSITIVE_INFINITY,
      );
      expect(vi.mocked(session.setAccessLevel).mock.invocationCallOrder[0]).toBeLessThan(
        vi.mocked(storageCall).mock.invocationCallOrder[0] ?? Number.POSITIVE_INFINITY,
      );
    },
  );

  it.each([
    ['short state', { state: 'short' }],
    ['control character in nonce', { nonce: `${'n'.repeat(42)}\u0000` }],
    ['invalid Extension ID', { redirectUri: `https://${'a'.repeat(31)}.chromiumapp.org/` }],
    ['redirect port', { redirectUri: `https://${extensionId}.chromiumapp.org:444/` }],
    ['redirect path', { redirectUri: `https://${extensionId}.chromiumapp.org/callback` }],
  ])('clears a corrupt persisted attempt with %s', async (_name, corruptFields) => {
    const local = storageArea();
    const session = storageArea({
      'jobpilot.auth.attempt': { ...validAttempt, ...corruptFields },
    });
    const store = new ChromeAuthStorage({ local, session });

    await expect(store.loadAttempt()).rejects.toEqual(
      new ExtensionAuthError('AUTHENTICATION_REQUIRED'),
    );
    expect(session.remove).toHaveBeenCalledWith('jobpilot.auth.attempt');
  });
});
