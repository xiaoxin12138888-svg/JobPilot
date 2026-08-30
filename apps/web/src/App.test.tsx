import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { App } from './App';

afterEach(cleanup);

describe('App', () => {
  it('renders the Web identity, environment, and connected API status', async () => {
    const healthCheck = vi.fn().mockResolvedValue({
      status: 'ok',
      service: 'jobpilot-api',
    });

    render(<App environment="test" healthCheck={healthCheck} />);

    expect(screen.getByRole('heading', { name: 'JobPilot' })).toBeInTheDocument();
    expect(screen.getByText('Application: Web')).toBeInTheDocument();
    expect(screen.getByText('Environment: test')).toBeInTheDocument();
    expect(await screen.findByText('API connection status: Connected')).toBeInTheDocument();
  });

  it('shows an unavailable status when the health request fails', async () => {
    const healthCheck = vi.fn().mockRejectedValue(new Error('API unavailable'));

    render(<App environment="test" healthCheck={healthCheck} />);

    expect(await screen.findByText('API connection status: Unavailable')).toBeInTheDocument();
  });
});
