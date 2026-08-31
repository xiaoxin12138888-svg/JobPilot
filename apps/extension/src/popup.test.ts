import { fireEvent, screen, waitFor } from '@testing-library/dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { initializePopup } from './popup';

const healthyResponse = { status: 'ok', service: 'jobpilot-api' } as const;

function renderPopupRoot(): HTMLElement {
  document.body.innerHTML = '<section id="popup-content" aria-live="polite"></section>';
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
  it('shows checking immediately and then reports the local service as available', async () => {
    const root = renderPopupRoot();
    const health = deferred<typeof healthyResponse>();
    const getHealth = vi.fn().mockReturnValue(health.promise);

    const initialization = initializePopup({ getHealth });

    expect(root.dataset.state).toBe('checking');
    expect(root).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByText('正在检查本机 JobPilot…')).toBeVisible();

    health.resolve(healthyResponse);
    await initialization;

    expect(getHealth).toHaveBeenCalledOnce();
    expect(root.dataset.state).toBe('available');
    expect(root).toHaveAttribute('aria-busy', 'false');
    expect(screen.getByText('本机 JobPilot 可用')).toBeVisible();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('maps health failures to a fixed unavailable state without exposing details', async () => {
    const root = renderPopupRoot();
    const getHealth = vi.fn().mockRejectedValue(new Error('private transport detail'));

    await initializePopup({ getHealth });

    expect(root.dataset.state).toBe('unavailable');
    expect(screen.getByText('本机 JobPilot 不可用')).toBeVisible();
    expect(screen.getByText('请确认本机服务已启动，然后重试。')).toBeVisible();
    expect(screen.getByRole('button', { name: '重试' })).toBeEnabled();
    expect(document.body.textContent).not.toContain('private transport detail');
  });

  it('checks health again after retry and recovers to available', async () => {
    const root = renderPopupRoot();
    const retryHealth = deferred<typeof healthyResponse>();
    const getHealth = vi
      .fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockReturnValueOnce(retryHealth.promise);
    await initializePopup({ getHealth });

    fireEvent.click(screen.getByRole('button', { name: '重试' }));

    expect(root.dataset.state).toBe('checking');
    expect(screen.getByText('正在检查本机 JobPilot…')).toBeVisible();
    retryHealth.resolve(healthyResponse);
    await waitFor(() => expect(root.dataset.state).toBe('available'));
    expect(getHealth).toHaveBeenCalledTimes(2);
  });

  it('contains no account, authentication, or remote navigation controls', async () => {
    renderPopupRoot();

    await initializePopup({ getHealth: vi.fn().mockResolvedValue(healthyResponse) });

    expect(document.body.textContent).not.toMatch(/登录|退出|账户|用户|OAuth|PKCE|token/iu);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });
});
