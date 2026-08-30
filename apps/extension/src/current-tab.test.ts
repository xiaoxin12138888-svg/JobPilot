import { afterEach, describe, expect, it, vi } from 'vitest';

import { getCurrentTabUrl } from './current-tab';

afterEach(() => vi.unstubAllGlobals());

describe('getCurrentTabUrl', () => {
  it('reads only the active tab in the current window', async () => {
    const query = vi.fn().mockResolvedValue([{ url: 'https://example.com/jobs/123' }]);
    vi.stubGlobal('chrome', { tabs: { query } });

    await expect(getCurrentTabUrl()).resolves.toBe('https://example.com/jobs/123');
    expect(query).toHaveBeenCalledWith({ active: true, currentWindow: true });
  });

  it('returns null when the active tab URL is unavailable', async () => {
    vi.stubGlobal('chrome', { tabs: { query: vi.fn().mockResolvedValue([{}]) } });

    await expect(getCurrentTabUrl()).resolves.toBeNull();
  });
});
