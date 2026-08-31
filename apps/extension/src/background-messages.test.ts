import type { UserView } from '@jobpilot/api-client';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ExtensionAuthError } from './auth/errors';
import {
  createPopupMessageHandler,
  createPopupMessageListener,
  isTrustedPopupSender,
  type PopupBackgroundDependencies,
  type PopupRuntimeBoundary,
} from './background-messages';

const runtime: PopupRuntimeBoundary = {
  id: 'a'.repeat(32),
  getURL: (path: string) => `chrome-extension://${'a'.repeat(32)}/${path}`,
};

const user: UserView = {
  id: 'user-1',
  email: 'user@example.com',
  displayName: 'Lin',
  locale: 'zh-CN',
  timeZone: 'Asia/Shanghai',
  createdAt: '2026-08-30T02:15:00Z',
  updatedAt: '2026-08-30T02:15:00Z',
};

function createDependencies(
  overrides: Partial<PopupBackgroundDependencies> = {},
): PopupBackgroundDependencies {
  return {
    authService: {
      restoreCurrentUser: vi.fn().mockResolvedValue(null),
      signIn: vi.fn().mockResolvedValue(user),
      signOut: vi.fn().mockResolvedValue({ status: 'confirmed' }),
    },
    openWebApp: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

function trustedSender(): chrome.runtime.MessageSender {
  return {
    id: runtime.id,
    origin: `chrome-extension://${runtime.id}`,
    url: runtime.getURL('popup.html'),
  };
}

afterEach(() => vi.restoreAllMocks());

describe('isTrustedPopupSender', () => {
  it('accepts only the extension popup top-level context', () => {
    expect(isTrustedPopupSender(trustedSender(), runtime)).toBe(true);
    const senderWithoutOrigin = trustedSender();
    delete senderWithoutOrigin.origin;
    expect(isTrustedPopupSender(senderWithoutOrigin, runtime)).toBe(true);
  });

  it.each([
    ['missing id', { url: runtime.getURL('popup.html') }],
    ['wrong id', { ...trustedSender(), id: 'b'.repeat(32) }],
    ['another extension page', { ...trustedSender(), url: runtime.getURL('options.html') }],
    ['wrong origin', { ...trustedSender(), origin: 'https://attacker.example.invalid' }],
    [
      'content script tab',
      {
        ...trustedSender(),
        tab: { id: 7 } as chrome.tabs.Tab,
        url: 'https://jobs.example.invalid/detail',
        origin: 'https://jobs.example.invalid',
      },
    ],
  ])('rejects %s', (_caseName, sender) => {
    expect(isTrustedPopupSender(sender as chrome.runtime.MessageSender, runtime)).toBe(false);
  });
});

describe('createPopupMessageHandler', () => {
  it('restores signed-out and signed-in popup-safe state', async () => {
    const signedOut = createPopupMessageHandler(createDependencies());
    await expect(signedOut({ type: 'GET_AUTH_STATE' })).resolves.toEqual({
      ok: true,
      state: { status: 'signed-out' },
    });

    const leakedUser = { ...user, accessToken: 'must-not-cross-the-message-boundary' };
    const signedIn = createPopupMessageHandler(
      createDependencies({
        authService: {
          restoreCurrentUser: vi.fn().mockResolvedValue(leakedUser),
          signIn: vi.fn().mockResolvedValue(leakedUser),
          signOut: vi.fn().mockResolvedValue({ status: 'confirmed' }),
        },
      }),
    );
    const response = await signedIn({ type: 'GET_AUTH_STATE' });

    expect(response).toEqual({
      ok: true,
      state: {
        status: 'signed-in',
        user: { id: 'user-1', email: 'user@example.com', displayName: 'Lin' },
      },
    });
    expect(JSON.stringify(response)).not.toContain('accessToken');
  });

  it('routes sign-in, each sign-out result, and configured Web opening', async () => {
    const dependencies = createDependencies();
    const handle = createPopupMessageHandler(dependencies);

    await expect(handle({ type: 'SIGN_IN' })).resolves.toEqual({
      ok: true,
      state: {
        status: 'signed-in',
        user: { id: 'user-1', email: 'user@example.com', displayName: 'Lin' },
      },
    });
    expect(dependencies.authService.signIn).toHaveBeenCalledOnce();

    for (const status of ['confirmed', 'not_applicable', 'unconfirmed'] as const) {
      vi.mocked(dependencies.authService.signOut).mockResolvedValueOnce({ status });
      await expect(handle({ type: 'SIGN_OUT' })).resolves.toEqual({
        ok: true,
        state: { status: 'signed-out' },
        revokeStatus: status,
      });
    }

    await expect(handle({ type: 'OPEN_WEB_APP' })).resolves.toEqual({ ok: true });
    expect(dependencies.openWebApp).toHaveBeenCalledOnce();
  });

  it('maps expected and unexpected failures to bounded popup-safe responses', async () => {
    const cancelled = createPopupMessageHandler(
      createDependencies({
        authService: {
          restoreCurrentUser: vi
            .fn()
            .mockRejectedValue(new ExtensionAuthError('AUTHENTICATION_REQUIRED')),
          signIn: vi.fn().mockRejectedValue(new ExtensionAuthError('AUTH_CANCELLED')),
          signOut: vi.fn().mockRejectedValue(new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE')),
        },
        openWebApp: vi.fn().mockRejectedValue(new Error('browser detail must stay private')),
      }),
    );

    await expect(cancelled({ type: 'GET_AUTH_STATE' })).resolves.toEqual({
      ok: true,
      state: { status: 'signed-out' },
    });
    await expect(cancelled({ type: 'SIGN_IN' })).resolves.toEqual({
      ok: false,
      error: 'AUTH_CANCELLED',
    });
    await expect(cancelled({ type: 'SIGN_OUT' })).resolves.toEqual({
      ok: false,
      error: 'AUTH_STORAGE_UNAVAILABLE',
    });
    await expect(cancelled({ type: 'OPEN_WEB_APP' })).resolves.toEqual({
      ok: false,
      error: 'OPEN_WEB_APP_FAILED',
    });

    const unavailable = createPopupMessageHandler(
      createDependencies({
        authService: {
          restoreCurrentUser: vi.fn().mockRejectedValue(new Error('provider detail')),
          signIn: vi.fn().mockResolvedValue(user),
          signOut: vi.fn().mockResolvedValue({ status: 'confirmed' }),
        },
      }),
    );
    await expect(unavailable({ type: 'GET_AUTH_STATE' })).resolves.toEqual({
      ok: false,
      error: 'AUTH_UNAVAILABLE',
    });
  });
});

describe('createPopupMessageListener', () => {
  it('rejects untrusted senders and malformed messages with zero side effects', () => {
    const dependencies = createDependencies();
    const listener = createPopupMessageListener({ dependencies, runtime });
    const sendResponse = vi.fn();

    expect(
      listener({ type: 'SIGN_IN' }, { ...trustedSender(), id: 'b'.repeat(32) }, sendResponse),
    ).toBe(false);
    expect(sendResponse).not.toHaveBeenCalled();

    expect(
      listener({ type: 'SIGN_IN', accessToken: 'secret' }, trustedSender(), sendResponse),
    ).toBe(false);
    expect(sendResponse).toHaveBeenCalledWith({ ok: false, error: 'INVALID_REQUEST' });
    expect(dependencies.authService.signIn).not.toHaveBeenCalled();
    expect(dependencies.openWebApp).not.toHaveBeenCalled();
  });

  it('returns literal true synchronously and responds asynchronously for valid messages', async () => {
    const dependencies = createDependencies();
    const listener = createPopupMessageListener({ dependencies, runtime });
    let resolveResponse: (value: unknown) => void = () => undefined;
    const response = new Promise<unknown>((resolve) => {
      resolveResponse = resolve;
    });

    const returnValue = listener({ type: 'SIGN_IN' }, trustedSender(), resolveResponse);

    expect(returnValue).toBe(true);
    expect(returnValue).not.toBeInstanceOf(Promise);
    await expect(response).resolves.toEqual({
      ok: true,
      state: {
        status: 'signed-in',
        user: { id: 'user-1', email: 'user@example.com', displayName: 'Lin' },
      },
    });
  });

  it('contains synchronous dependency throws and returns only a sanitized fallback', async () => {
    const dependencies = createDependencies({
      authService: {
        restoreCurrentUser: vi.fn().mockResolvedValue(null),
        signIn: vi.fn(() => {
          throw new Error('authorization-code provider detail');
        }),
        signOut: vi.fn().mockResolvedValue({ status: 'confirmed' }),
      },
    });
    const listener = createPopupMessageListener({ dependencies, runtime });
    let resolveResponse: (value: unknown) => void = () => undefined;
    const response = new Promise<unknown>((resolve) => {
      resolveResponse = resolve;
    });

    expect(listener({ type: 'SIGN_IN' }, trustedSender(), resolveResponse)).toBe(true);
    await expect(response).resolves.toEqual({ ok: false, error: 'AUTH_UNAVAILABLE' });
  });
});
