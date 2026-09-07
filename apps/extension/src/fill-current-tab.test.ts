import { afterEach, describe, expect, it, vi } from 'vitest';

import type { FillPlanItem, FormFieldDescriptor } from './autofill-types';
import { fillCurrentApplicationForm } from './fill-current-tab';
import { fillApplicationForm } from './fill-executor';
import type { FormScanSession } from './scan-current-tab';

const nameField: FormFieldDescriptor = {
  ref: 'id:full-name',
  label: '姓名',
  kind: 'TEXT',
  type: 'text',
  name: 'candidate_name',
  id: 'full-name',
  required: true,
  placeholder: null,
  autocomplete: 'name',
  options: [],
};
const cityField: FormFieldDescriptor = {
  ...nameField,
  ref: 'id:city',
  label: '城市方向',
  name: 'city',
  id: 'city',
  required: false,
  autocomplete: null,
};
const checkboxField: FormFieldDescriptor = {
  ...nameField,
  ref: 'id:agreement',
  label: '同意协议',
  kind: 'CHECKBOX',
  type: 'checkbox',
  name: 'agreement',
  id: 'agreement',
  required: false,
  autocomplete: null,
};
const session: FormScanSession = {
  pageUrl: 'https://careers.example.test/apply/42',
  scanToken: 'scan-token-42',
  tabId: 71,
  fields: [nameField, cityField, checkboxField],
};
const completedResult = {
  status: 'COMPLETED',
  attempted: 1,
  filled: 1,
  failures: [],
} as const;

function planItem(overrides: Partial<FillPlanItem> = {}): FillPlanItem {
  return {
    fieldRef: 'id:full-name',
    pageLabel: '姓名',
    canonicalKey: 'name',
    proposedValue: '示例用户',
    status: 'READY',
    selected: true,
    ...overrides,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('fillCurrentApplicationForm', () => {
  it('injects only selected ready or user-confirmed review items from the scan session', async () => {
    const executeScript = vi.fn().mockResolvedValue([{ frameId: 0, result: completedResult }]);
    vi.stubGlobal('chrome', {
      scripting: { executeScript },
      tabs: { query: vi.fn().mockResolvedValue([{ id: 71, url: session.pageUrl }]) },
    });
    const plan = [
      planItem(),
      planItem({
        fieldRef: 'id:city',
        pageLabel: '城市方向',
        canonicalKey: 'current_city',
        proposedValue: '示例市',
        status: 'REVIEW_REQUIRED',
        selected: false,
      }),
      planItem({
        fieldRef: 'id:agreement',
        pageLabel: '同意协议',
        canonicalKey: null,
        proposedValue: 'true',
        status: 'MANUAL',
        selected: true,
      }),
    ];

    await expect(fillCurrentApplicationForm(session, plan)).resolves.toEqual(completedResult);
    expect(executeScript).toHaveBeenCalledWith({
      args: [
        {
          pageUrl: session.pageUrl,
          scanToken: session.scanToken,
          fields: [{ field: nameField, value: '示例用户' }],
        },
      ],
      func: fillApplicationForm,
      target: { tabId: 71 },
    });
  });

  it('allows an explicitly selected review item', async () => {
    const executeScript = vi.fn().mockResolvedValue([{ frameId: 0, result: completedResult }]);
    vi.stubGlobal('chrome', {
      scripting: { executeScript },
      tabs: { query: vi.fn().mockResolvedValue([{ id: 71, url: session.pageUrl }]) },
    });

    await fillCurrentApplicationForm(session, [
      planItem({
        fieldRef: 'id:city',
        canonicalKey: 'current_city',
        proposedValue: '示例市',
        status: 'REVIEW_REQUIRED',
      }),
    ]);

    expect(executeScript).toHaveBeenCalledWith(
      expect.objectContaining({
        args: [expect.objectContaining({ fields: [{ field: cityField, value: '示例市' }] })],
      }),
    );
  });

  it('returns page changed without injection when the active tab no longer matches the scan', async () => {
    const executeScript = vi.fn();
    vi.stubGlobal('chrome', {
      scripting: { executeScript },
      tabs: {
        query: vi
          .fn()
          .mockResolvedValue([{ id: 71, url: 'https://careers.example.test/apply/changed' }]),
      },
    });

    await expect(fillCurrentApplicationForm(session, [planItem()])).resolves.toEqual({
      status: 'PAGE_CHANGED',
      attempted: 0,
      filled: 0,
      failures: [],
    });
    expect(executeScript).not.toHaveBeenCalled();
  });

  it('does not inject when the user selected no fillable item', async () => {
    const executeScript = vi.fn();
    vi.stubGlobal('chrome', {
      scripting: { executeScript },
      tabs: { query: vi.fn().mockResolvedValue([{ id: 71, url: session.pageUrl }]) },
    });

    await expect(
      fillCurrentApplicationForm(session, [planItem({ selected: false })]),
    ).resolves.toEqual({ status: 'COMPLETED', attempted: 0, filled: 0, failures: [] });
    expect(executeScript).not.toHaveBeenCalled();
  });

  it('fails closed when Chrome returns a malformed execution result', async () => {
    vi.stubGlobal('chrome', {
      scripting: {
        executeScript: vi.fn().mockResolvedValue([{ frameId: 0, result: { ok: true } }]),
      },
      tabs: { query: vi.fn().mockResolvedValue([{ id: 71, url: session.pageUrl }]) },
    });

    await expect(fillCurrentApplicationForm(session, [planItem()])).rejects.toThrow(
      '未能确认页面填写结果',
    );
  });
});
