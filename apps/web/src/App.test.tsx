import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiClientError, type ApiClient } from '@jobpilot/api-client';

import { App } from './App';

afterEach(cleanup);

describe('App', () => {
  it('renders a clear loading state while the current session is checked', () => {
    const apiClient = createAuthClient({
      getCurrentUser: vi.fn<ApiClient['getCurrentUser']>(() => new Promise<never>(() => undefined)),
    });

    render(<App apiClient={apiClient} />);

    expect(screen.getByRole('heading', { name: 'JobPilot' })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('正在检查登录状态');
  });

  it('renders the signed-out state and fixed login action for an unauthenticated visitor', async () => {
    const apiClient = createAuthClient({
      getCurrentUser: vi
        .fn<ApiClient['getCurrentUser']>()
        .mockRejectedValue(new ApiClientError(401, 'AUTHENTICATION_REQUIRED')),
    });

    render(<App apiClient={apiClient} />);

    expect(await screen.findByText('登录后继续使用 JobPilot')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '登录' })).toHaveAttribute(
      'href',
      'http://localhost:8000/api/v1/auth/web/authorize?intent=login&returnTo=%2F',
    );
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(apiClient.getWebCsrfToken).not.toHaveBeenCalled();
  });

  it('renders the authenticated JobPilot user returned by /auth/me', async () => {
    const apiClient = createAuthClient();

    render(<App apiClient={apiClient} />);

    expect(await screen.findByText('欢迎，Lin')).toBeInTheDocument();
    expect(screen.getByText('lin@example.com')).toBeInTheDocument();
    expect(screen.getByText('019d4a83-cf8c-7f77-a4f0-2cc4131e3138')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '退出' })).toBeEnabled();
    expect(apiClient.getWebCsrfToken).toHaveBeenCalledOnce();
  });

  it('logs out with the in-memory session-bound CSRF token', async () => {
    const apiClient = createAuthClient();

    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '退出' }));

    expect(await screen.findByText('登录后继续使用 JobPilot')).toBeInTheDocument();
    expect(apiClient.logoutWebSession).toHaveBeenCalledWith('csrf-token');
    expect(screen.getByRole('link', { name: '登录' })).toHaveFocus();
  });

  it('does not start a second logout while the first request is pending', async () => {
    let finishLogout: (() => void) | undefined;
    const pendingLogout = new Promise<void>((resolve) => {
      finishLogout = resolve;
    });
    const apiClient = createAuthClient({
      logoutWebSession: vi.fn<ApiClient['logoutWebSession']>().mockReturnValue(pendingLogout),
    });

    render(<App apiClient={apiClient} />);
    const logoutButton = await screen.findByRole('button', { name: '退出' });
    fireEvent.click(logoutButton);
    fireEvent.click(logoutButton);

    expect(apiClient.logoutWebSession).toHaveBeenCalledOnce();
    await act(async () => finishLogout?.());
    expect(await screen.findByText('登录后继续使用 JobPilot')).toBeInTheDocument();
  });

  it('recovers to signed out when the session expires between /me and /csrf', async () => {
    const apiClient = createAuthClient({
      getWebCsrfToken: vi
        .fn<ApiClient['getWebCsrfToken']>()
        .mockRejectedValue(new ApiClientError(401, 'AUTHENTICATION_REQUIRED')),
    });

    render(<App apiClient={apiClient} />);

    expect(await screen.findByText('登录后继续使用 JobPilot')).toBeInTheDocument();
    expect(apiClient.logoutWebSession).not.toHaveBeenCalled();
  });

  it('does not request a CSRF token after the session check is abandoned', async () => {
    let resolveCurrentUser: ((user: typeof currentUser) => void) | undefined;
    const pendingCurrentUser = new Promise<typeof currentUser>((resolve) => {
      resolveCurrentUser = resolve;
    });
    const apiClient = createAuthClient({
      getCurrentUser: vi.fn<ApiClient['getCurrentUser']>().mockReturnValue(pendingCurrentUser),
    });

    const { unmount } = render(<App apiClient={apiClient} />);
    unmount();
    await act(async () => {
      resolveCurrentUser?.(currentUser);
      await pendingCurrentUser;
    });

    expect(apiClient.getWebCsrfToken).not.toHaveBeenCalled();
  });

  it('fails closed when the CSRF boundary is temporarily unavailable', async () => {
    const apiClient = createAuthClient({
      getWebCsrfToken: vi
        .fn<ApiClient['getWebCsrfToken']>()
        .mockRejectedValue(new ApiClientError(503, 'DEPENDENCY_UNAVAILABLE')),
    });

    render(<App apiClient={apiClient} />);

    expect(await screen.findByRole('alert')).toHaveTextContent('暂时无法确认登录状态');
    expect(screen.queryByText('欢迎，Lin')).not.toBeInTheDocument();
  });

  it('falls back to verified email when displayName is not set', async () => {
    const apiClient = createAuthClient({
      getCurrentUser: vi.fn<ApiClient['getCurrentUser']>().mockResolvedValue({
        ...currentUser,
        displayName: null,
      }),
    });

    render(<App apiClient={apiClient} />);

    expect(await screen.findByText('欢迎，lin@example.com')).toBeInTheDocument();
  });

  it('keeps the visible user and reports uncertainty when logout fails', async () => {
    const apiClient = createAuthClient({
      logoutWebSession: vi
        .fn<ApiClient['logoutWebSession']>()
        .mockRejectedValue(new ApiClientError(503, 'DEPENDENCY_UNAVAILABLE')),
    });

    render(<App apiClient={apiClient} />);
    fireEvent.click(await screen.findByRole('button', { name: '退出' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('暂时无法安全退出');
    expect(screen.getByText('欢迎，Lin')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '退出' })).toBeEnabled();
  });

  it('shows a bounded callback error without making a session request', () => {
    const apiClient = createAuthClient();

    render(<App apiClient={apiClient} hasAuthenticationError />);

    expect(screen.getByRole('alert')).toHaveTextContent('登录未完成');
    expect(screen.getByText('请重新登录，或稍后再试。')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '重新登录' })).toHaveAttribute(
      'href',
      apiClient.getWebLoginUrl(),
    );
    expect(apiClient.getCurrentUser).not.toHaveBeenCalled();
  });

  it('retries a transient session-status failure and restores the signed-in state', async () => {
    const apiClient = createAuthClient({
      getCurrentUser: vi
        .fn<ApiClient['getCurrentUser']>()
        .mockRejectedValueOnce(new Error('offline'))
        .mockResolvedValueOnce(currentUser),
    });

    render(<App apiClient={apiClient} />);

    expect(await screen.findByRole('alert')).toHaveTextContent('暂时无法确认登录状态');
    fireEvent.click(screen.getByRole('button', { name: '重试' }));

    expect(await screen.findByText('欢迎，Lin')).toBeInTheDocument();
    expect(apiClient.getCurrentUser).toHaveBeenCalledTimes(2);
  });
});

const currentUser = {
  id: '019d4a83-cf8c-7f77-a4f0-2cc4131e3138',
  email: 'lin@example.com',
  displayName: 'Lin',
  locale: 'zh-CN',
  timeZone: 'Asia/Shanghai',
  createdAt: '2026-08-30T02:15:00Z',
  updatedAt: '2026-08-30T02:15:00Z',
};

function createAuthClient(overrides: Partial<ApiClient> = {}): ApiClient {
  return {
    getHealth: vi.fn().mockResolvedValue({ status: 'ok', service: 'jobpilot-api' }),
    getCurrentUser: vi.fn().mockResolvedValue(currentUser),
    getWebCsrfToken: vi.fn().mockResolvedValue('csrf-token'),
    logoutWebSession: vi.fn().mockResolvedValue(undefined),
    getWebLoginUrl: vi
      .fn()
      .mockReturnValue('http://localhost:8000/api/v1/auth/web/authorize?intent=login&returnTo=%2F'),
    ...overrides,
  };
}
