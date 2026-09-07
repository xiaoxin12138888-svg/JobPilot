import { afterEach, describe, expect, it, vi } from 'vitest';

import { scanApplicationForm } from './form-scanner';
import { scanCurrentApplicationForm } from './scan-current-tab';

const scanResult = {
  pageUrl: 'https://careers.example.test/apply/42',
  fields: [
    {
      ref: 'id:full-name',
      label: '姓名',
      kind: 'TEXT',
      type: 'text',
      name: 'name',
      id: 'full-name',
      required: true,
      placeholder: null,
      autocomplete: 'name',
      options: [],
    },
  ],
} as const;

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('scanCurrentApplicationForm', () => {
  it('scans one user-selected HTTP tab with one explicit injection', async () => {
    const query = vi.fn().mockResolvedValue([{ id: 71, url: scanResult.pageUrl }]);
    const executeScript = vi.fn().mockResolvedValue([{ frameId: 0, result: scanResult }]);
    vi.stubGlobal('chrome', { scripting: { executeScript }, tabs: { query } });

    const session = await scanCurrentApplicationForm();

    expect(query).toHaveBeenCalledWith({ active: true, currentWindow: true });
    expect(executeScript).toHaveBeenCalledWith({
      func: scanApplicationForm,
      target: { tabId: 71 },
    });
    expect(session).toEqual({
      ...scanResult,
      scanToken: expect.any(String),
      tabId: 71,
    });
    expect(session.scanToken).not.toBe('');
  });

  it.each([
    ['missing tab', []],
    ['missing URL', [{ id: 71 }]],
    ['missing tab ID', [{ url: scanResult.pageUrl }]],
    ['browser page', [{ id: 71, url: 'chrome://settings/' }]],
    ['credentialed URL', [{ id: 71, url: 'https://user:pass@example.test/apply' }]],
  ])('rejects %s without scanning', async (_label, tabs) => {
    const executeScript = vi.fn();
    vi.stubGlobal('chrome', {
      scripting: { executeScript },
      tabs: { query: vi.fn().mockResolvedValue(tabs) },
    });

    await expect(scanCurrentApplicationForm()).rejects.toThrow('当前页面不支持表单扫描');
    expect(executeScript).not.toHaveBeenCalled();
  });

  it.each([
    ['missing result', [{ frameId: 0 }]],
    ['wrong page URL', [{ frameId: 0, result: { ...scanResult, pageUrl: 'file:///private' } }]],
    [
      'unknown field kind',
      [
        {
          frameId: 0,
          result: { ...scanResult, fields: [{ ...scanResult.fields[0], kind: 'SECRET' }] },
        },
      ],
    ],
  ])('fails closed for a malformed injected %s', async (_label, results) => {
    vi.stubGlobal('chrome', {
      scripting: { executeScript: vi.fn().mockResolvedValue(results) },
      tabs: { query: vi.fn().mockResolvedValue([{ id: 71, url: scanResult.pageUrl }]) },
    });

    await expect(scanCurrentApplicationForm()).rejects.toThrow('未能安全读取当前表单');
  });
});
