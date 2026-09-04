import { afterEach, describe, expect, it, vi } from 'vitest';

import { captureBossJobFromPage } from './boss-adapter';
import { captureCurrentBossJob } from './capture-current-tab';

const capturedResult = {
  draft: {
    company: '示例科技',
    description: '岗位描述',
    location: '北京',
    salaryText: '200-250元/天',
    source: 'boss',
    sourceUrl: 'https://www.zhipin.com/job_detail/fixture_123.html',
    title: '产品经理',
  },
  warnings: [],
} as const;

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('captureCurrentBossJob', () => {
  it('queries only the active tab and performs one explicit script injection', async () => {
    const query = vi.fn().mockResolvedValue([
      {
        id: 42,
        url: 'https://www.zhipin.com/job_detail/fixture_123.html?pk=list',
      },
    ]);
    const executeScript = vi.fn().mockResolvedValue([{ frameId: 0, result: capturedResult }]);
    vi.stubGlobal('chrome', { scripting: { executeScript }, tabs: { query } });

    await expect(captureCurrentBossJob()).resolves.toEqual(capturedResult);
    expect(query).toHaveBeenCalledWith({ active: true, currentWindow: true });
    expect(executeScript).toHaveBeenCalledOnce();
    expect(executeScript).toHaveBeenCalledWith({
      func: captureBossJobFromPage,
      target: { tabId: 42 },
    });
  });

  it.each([
    ['missing tab', []],
    ['missing URL', [{ id: 42 }]],
    ['missing tab ID', [{ url: 'https://www.zhipin.com/job_detail/fixture_123.html' }]],
    ['non-BOSS page', [{ id: 42, url: 'https://example.com/' }]],
  ])('returns unsupported for %s without injecting', async (_label, tabs) => {
    const query = vi.fn().mockResolvedValue(tabs);
    const executeScript = vi.fn();
    vi.stubGlobal('chrome', { scripting: { executeScript }, tabs: { query } });

    await expect(captureCurrentBossJob()).resolves.toEqual({ status: 'unsupported' });
    expect(executeScript).not.toHaveBeenCalled();
  });

  it('lets the BossAdapter reject a BOSS non-detail page after one local injection', async () => {
    const query = vi
      .fn()
      .mockResolvedValue([{ id: 42, url: 'https://www.zhipin.com/web/geek/job' }]);
    const executeScript = vi
      .fn()
      .mockResolvedValue([{ frameId: 0, result: { status: 'unsupported' } }]);
    vi.stubGlobal('chrome', { scripting: { executeScript }, tabs: { query } });

    await expect(captureCurrentBossJob()).resolves.toEqual({ status: 'unsupported' });
    expect(executeScript).toHaveBeenCalledOnce();
  });

  it('fails closed when Chrome returns no parser result', async () => {
    vi.stubGlobal('chrome', {
      scripting: { executeScript: vi.fn().mockResolvedValue([{ frameId: 0 }]) },
      tabs: {
        query: vi.fn().mockResolvedValue([
          {
            id: 42,
            url: 'https://www.zhipin.com/job_detail/fixture_123.html',
          },
        ]),
      },
    });

    await expect(captureCurrentBossJob()).rejects.toThrow('BOSS parser returned no result');
  });
});
