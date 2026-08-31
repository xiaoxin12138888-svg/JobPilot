import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ApiClient } from '@jobpilot/api-client';

import { App } from './App';

type HealthClient = Pick<ApiClient, 'getHealth'>;

const healthyResponse = { status: 'ok', service: 'jobpilot-api' } as const;

afterEach(cleanup);

describe('App', () => {
  it('renders a clear checking state while the local API health request is pending', () => {
    const apiClient = createHealthClient(
      vi.fn<HealthClient['getHealth']>(() => new Promise<never>(() => undefined)),
    );

    render(<App apiClient={apiClient} />);

    expect(screen.getByRole('heading', { name: 'JobPilot' })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('正在连接本地服务');
    expect(screen.getByRole('status')).toHaveAttribute('aria-busy', 'true');
  });

  it('renders the ready state without account or authentication actions', async () => {
    render(<App apiClient={createHealthClient()} />);

    expect(await screen.findByRole('heading', { name: '本地服务已就绪' })).toBeInTheDocument();
    expect(screen.getByText('JobPilot 已连接到本机 API。')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /登录/u })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '退出' })).not.toBeInTheDocument();
  });

  it('renders an actionable unavailable state when the local API cannot be reached', async () => {
    const apiClient = createHealthClient(
      vi.fn<HealthClient['getHealth']>().mockRejectedValue(new Error('offline')),
    );

    render(<App apiClient={apiClient} />);

    expect(await screen.findByRole('alert')).toHaveTextContent('无法连接本地服务');
    expect(screen.getByText('请确认本机 JobPilot API 已启动，然后重试。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重试' })).toBeEnabled();
  });

  it('retries a failed health request and renders the recovered ready state', async () => {
    const getHealth = vi
      .fn<HealthClient['getHealth']>()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(healthyResponse);

    render(<App apiClient={createHealthClient(getHealth)} />);

    expect(await screen.findByRole('alert')).toHaveTextContent('无法连接本地服务');
    fireEvent.click(screen.getByRole('button', { name: '重试' }));

    expect(screen.getByRole('status')).toHaveTextContent('正在连接本地服务');
    expect(await screen.findByRole('heading', { name: '本地服务已就绪' })).toBeInTheDocument();
    expect(getHealth).toHaveBeenCalledTimes(2);
  });

  it('ignores a stale health failure after the API client changes', async () => {
    let rejectStaleRequest: ((reason?: unknown) => void) | undefined;
    const staleRequest = new Promise<never>((_resolve, reject) => {
      rejectStaleRequest = reject;
    });
    const staleClient = createHealthClient(
      vi.fn<HealthClient['getHealth']>().mockReturnValue(staleRequest),
    );
    const currentClient = createHealthClient();
    const { rerender } = render(<App apiClient={staleClient} />);

    rerender(<App apiClient={currentClient} />);
    expect(await screen.findByRole('heading', { name: '本地服务已就绪' })).toBeInTheDocument();

    await act(async () => {
      rejectStaleRequest?.(new Error('stale failure'));
      await staleRequest.catch(() => undefined);
    });

    expect(screen.getByRole('heading', { name: '本地服务已就绪' })).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('returns to checking when a ready view receives a new pending API client', async () => {
    const { rerender } = render(<App apiClient={createHealthClient()} />);

    expect(await screen.findByRole('heading', { name: '本地服务已就绪' })).toBeInTheDocument();

    const pendingClient = createHealthClient(
      vi.fn<HealthClient['getHealth']>(() => new Promise<never>(() => undefined)),
    );
    rerender(<App apiClient={pendingClient} />);

    expect(screen.getByRole('status')).toHaveTextContent('正在连接本地服务');
    expect(screen.getByRole('status')).toHaveAttribute('aria-busy', 'true');
    expect(screen.queryByRole('heading', { name: '本地服务已就绪' })).not.toBeInTheDocument();
  });
});

function createHealthClient(
  getHealth: HealthClient['getHealth'] = vi.fn().mockResolvedValue(healthyResponse),
): HealthClient {
  return { getHealth };
}
