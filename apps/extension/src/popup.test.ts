import { afterEach, describe, expect, it, vi } from 'vitest';

import { initializePopup } from './popup';

afterEach(() => {
  document.body.replaceChildren();
});

function renderPopupStatusElements() {
  document.body.innerHTML = `
    <p id="current-tab-url"></p>
    <p id="api-status"></p>
  `;
}

describe('initializePopup', () => {
  it('shows the current tab URL and connected API status', async () => {
    renderPopupStatusElements();

    await initializePopup({
      getCurrentTabUrl: vi.fn().mockResolvedValue('https://example.com/jobs/123'),
      getHealth: vi.fn().mockResolvedValue({ status: 'ok', service: 'jobpilot-api' }),
    });

    expect(document.querySelector('#current-tab-url')).toHaveTextContent(
      'Current tab URL: https://example.com/jobs/123',
    );
    expect(document.querySelector('#api-status')).toHaveTextContent(
      'API connection status: Connected',
    );
  });

  it('keeps failures isolated and displays unavailable states', async () => {
    renderPopupStatusElements();

    await initializePopup({
      getCurrentTabUrl: vi.fn().mockRejectedValue(new Error('Restricted tab')),
      getHealth: vi.fn().mockRejectedValue(new Error('API unavailable')),
    });

    expect(document.querySelector('#current-tab-url')).toHaveTextContent(
      'Current tab URL: Unavailable',
    );
    expect(document.querySelector('#api-status')).toHaveTextContent(
      'API connection status: Unavailable',
    );
  });
});
