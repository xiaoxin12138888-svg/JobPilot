import { fireEvent, screen, waitFor } from '@testing-library/dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { initializePopup } from './popup';

const signedOutResponse = {
  ok: true,
  state: { status: 'signed-out' },
} as const;

const signedInResponse = {
  ok: true,
  state: {
    status: 'signed-in',
    user: {
      id: 'user-1',
      email: 'user@example.com',
      displayName: 'Lin',
    },
  },
} as const;

function renderPopupRoot(): HTMLElement {
  document.body.innerHTML = `
    <section id="popup-content" aria-live="polite"></section>
  `;
  const root = document.getElementById('popup-content');
  if (root === null) {
    throw new Error('Test popup root was not created');
  }
  return root;
}

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

afterEach(() => {
  document.body.replaceChildren();
  vi.restoreAllMocks();
});

describe('initializePopup', () => {
  it('restores signed-out state with one credential-free intent', async () => {
    const root = renderPopupRoot();
    const sendMessage = vi.fn().mockResolvedValue(signedOutResponse);

    await initializePopup({ sendMessage });

    expect(sendMessage).toHaveBeenCalledOnce();
    expect(sendMessage).toHaveBeenCalledWith({ type: 'GET_AUTH_STATE' });
    expect(root.dataset.state).toBe('signed-out');
    expect(screen.getByText('尚未登录')).toBeVisible();
    expect(screen.getByRole('button', { name: '登录 JobPilot' })).toBeEnabled();
  });

  it('shows authenticating immediately, prevents duplicate sign-in, and renders the safe user', async () => {
    const root = renderPopupRoot();
    const signIn = deferred<unknown>();
    const sendMessage = vi
      .fn()
      .mockResolvedValueOnce(signedOutResponse)
      .mockReturnValueOnce(signIn.promise);
    await initializePopup({ sendMessage });
    const loginButton = screen.getByRole('button', { name: '登录 JobPilot' });

    fireEvent.click(loginButton);
    fireEvent.click(loginButton);

    expect(root.dataset.state).toBe('authenticating');
    expect(screen.getByText('正在登录...')).toBeVisible();
    expect(sendMessage).toHaveBeenCalledTimes(2);
    expect(sendMessage).toHaveBeenLastCalledWith({ type: 'SIGN_IN' });

    signIn.resolve(signedInResponse);
    await waitFor(() => expect(root.dataset.state).toBe('signed-in'));
    expect(screen.getByText('✓ 已登录')).toBeVisible();
    expect(screen.getByText('Lin')).toBeVisible();
    expect(screen.getByText('user@example.com')).toBeVisible();
    expect(screen.getByText('user-1')).toBeVisible();
    expect(screen.getByRole('button', { name: '打开 JobPilot' })).toBeEnabled();
    expect(screen.getByRole('button', { name: '退出' })).toBeEnabled();
  });

  it('renders user-controlled profile text without creating markup', async () => {
    renderPopupRoot();
    const sendMessage = vi.fn().mockResolvedValue({
      ...signedInResponse,
      state: {
        ...signedInResponse.state,
        user: {
          ...signedInResponse.state.user,
          displayName: '<img src=x onerror=alert(1)>',
        },
      },
    });

    await initializePopup({ sendMessage });

    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeVisible();
    expect(document.querySelector('img')).toBeNull();
  });

  it('falls back to verified email when display name is blank', async () => {
    renderPopupRoot();
    const sendMessage = vi.fn().mockResolvedValue({
      ...signedInResponse,
      state: {
        ...signedInResponse.state,
        user: { ...signedInResponse.state.user, displayName: '   ' },
      },
    });

    await initializePopup({ sendMessage });

    expect(screen.getAllByText('user@example.com')).toHaveLength(1);
  });

  it('opens only through the no-payload intent and keeps signed-in state on failure', async () => {
    const root = renderPopupRoot();
    const sendMessage = vi
      .fn()
      .mockResolvedValueOnce(signedInResponse)
      .mockResolvedValueOnce({ ok: false, error: 'OPEN_WEB_APP_FAILED' });
    await initializePopup({ sendMessage });

    fireEvent.click(screen.getByRole('button', { name: '打开 JobPilot' }));

    await waitFor(() => expect(screen.getByText('暂时无法打开 JobPilot，请重试。')).toBeVisible());
    expect(root.dataset.state).toBe('signed-in');
    expect(sendMessage).toHaveBeenLastCalledWith({ type: 'OPEN_WEB_APP' });
    expect(JSON.stringify(sendMessage.mock.calls.at(-1))).not.toContain('url');
  });

  it.each(['confirmed', 'not_applicable'] as const)(
    'returns to signed-out after a %s local logout result',
    async (revokeStatus) => {
      const root = renderPopupRoot();
      const sendMessage = vi
        .fn()
        .mockResolvedValueOnce(signedInResponse)
        .mockResolvedValueOnce({
          ok: true,
          state: { status: 'signed-out' },
          revokeStatus,
        });
      await initializePopup({ sendMessage });

      fireEvent.click(screen.getByRole('button', { name: '退出' }));

      expect(screen.getByText('正在退出...')).toBeVisible();
      await waitFor(() => expect(root.dataset.state).toBe('signed-out'));
      expect(sendMessage).toHaveBeenLastCalledWith({ type: 'SIGN_OUT' });
      expect(screen.getByText('尚未登录')).toBeVisible();
    },
  );

  it('shows a truthful revoke-unconfirmed state after local cleanup', async () => {
    const root = renderPopupRoot();
    const sendMessage = vi
      .fn()
      .mockResolvedValueOnce(signedInResponse)
      .mockResolvedValueOnce({
        ok: true,
        state: { status: 'signed-out' },
        revokeStatus: 'unconfirmed',
      });
    await initializePopup({ sendMessage });

    fireEvent.click(screen.getByRole('button', { name: '退出' }));

    await waitFor(() => expect(root.dataset.state).toBe('revoke-unconfirmed'));
    expect(screen.getByText(/已在本机退出，但远端授权状态未确认/u)).toBeVisible();
    expect(screen.getByRole('button', { name: '登录 JobPilot' })).toBeEnabled();
  });

  it('does not claim logout when local credential cleanup is unavailable', async () => {
    const root = renderPopupRoot();
    const sendMessage = vi
      .fn()
      .mockResolvedValueOnce(signedInResponse)
      .mockResolvedValueOnce({ ok: false, error: 'AUTH_STORAGE_UNAVAILABLE' });
    await initializePopup({ sendMessage });

    fireEvent.click(screen.getByRole('button', { name: '退出' }));

    await waitFor(() => expect(root.dataset.state).toBe('error'));
    expect(screen.getByText('退出未完成，请重试。')).toBeVisible();
    expect(screen.queryByText('尚未登录')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重试退出' })).toBeEnabled();
  });

  it('returns to signed-out when the user cancels interactive sign-in', async () => {
    const root = renderPopupRoot();
    const sendMessage = vi
      .fn()
      .mockResolvedValueOnce(signedOutResponse)
      .mockResolvedValueOnce({ ok: false, error: 'AUTH_CANCELLED' });
    await initializePopup({ sendMessage });

    fireEvent.click(screen.getByRole('button', { name: '登录 JobPilot' }));

    await waitFor(() => expect(root.dataset.state).toBe('signed-out'));
    expect(screen.queryByText(/OAuth|PKCE|JWT|Auth0/u)).not.toBeInTheDocument();
  });

  it('fails safely on a malformed credential-shaped response and can retry restore', async () => {
    const root = renderPopupRoot();
    const sendMessage = vi
      .fn()
      .mockResolvedValueOnce({
        ...signedOutResponse,
        accessToken: 'must-not-cross-the-message-boundary',
      })
      .mockResolvedValueOnce(signedOutResponse);

    await initializePopup({ sendMessage });

    expect(root.dataset.state).toBe('error');
    expect(document.body.textContent).not.toContain('must-not-cross-the-message-boundary');
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    await waitFor(() => expect(root.dataset.state).toBe('signed-out'));
    expect(sendMessage).toHaveBeenLastCalledWith({ type: 'GET_AUTH_STATE' });
  });

  it('maps runtime rejection to a fixed error without rendering raw details', async () => {
    const root = renderPopupRoot();
    const sendMessage = vi.fn().mockRejectedValue(new Error('provider callback secret detail'));

    await initializePopup({ sendMessage });

    expect(root.dataset.state).toBe('error');
    expect(screen.getByText('暂时无法读取登录状态，请重试。')).toBeVisible();
    expect(document.body.textContent).not.toContain('provider callback secret detail');
  });
});
