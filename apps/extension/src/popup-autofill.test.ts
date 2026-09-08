import { fireEvent, screen, waitFor } from '@testing-library/dom';
import type { AutofillProfile } from '@jobpilot/api-client';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { FillPlanItem, FormFieldDescriptor } from './autofill-types';
import { initializePopup } from './popup';
import type { FormScanSession } from './scan-current-tab';

const profile: AutofillProfile = {
  personal: {
    name: '示例用户',
    phone: '13800000000',
    email: 'candidate@example.test',
    currentCity: '示例市',
  },
  education: [
    { school: '示例大学', major: '信息工程', degree: '本科', start: '2022-09', end: '2026-06' },
  ],
  experience: [],
  projects: [],
  links: { github: null, portfolio: null, homepage: null },
  createdAt: '2026-09-07T08:00:00Z',
  updatedAt: '2026-09-07T08:00:00Z',
};

function field(
  ref: string,
  label: string,
  overrides: Partial<FormFieldDescriptor> = {},
): FormFieldDescriptor {
  return {
    ref,
    label,
    kind: 'TEXT',
    type: 'text',
    name: null,
    id: ref.startsWith('id:') ? ref.slice(3) : null,
    required: false,
    placeholder: null,
    autocomplete: null,
    options: [],
    ...overrides,
  };
}

const session: FormScanSession = {
  pageUrl: 'https://careers.example.test/apply/42',
  scanToken: 'popup-scan-token',
  tabId: 71,
  fields: [
    field('id:name', '姓名'),
    field('id:phone', '手机号'),
    field('id:email', '电子邮箱'),
    field('id:discipline-direction', '专业方向'),
    field('id:salary', '期望薪资'),
    field('id:agreement', '同意隐私条款', { kind: 'CHECKBOX', type: 'checkbox' }),
    field('id:resume', '上传简历', { kind: 'FILE', type: 'file' }),
    field('id:color', '最喜欢的颜色'),
  ],
};

function renderPopupRoot(): HTMLElement {
  document.body.innerHTML = '<section id="popup-content" aria-live="polite"></section>';
  return document.getElementById('popup-content')!;
}

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function autofillDependencies(overrides: Record<string, unknown> = {}) {
  return {
    closePopup: vi.fn(),
    fillCurrentForm: vi.fn().mockResolvedValue({
      status: 'COMPLETED',
      attempted: 3,
      filled: 3,
      failures: [],
    }),
    getAutofillProfile: vi.fn().mockResolvedValue({ profile }),
    openProfile: vi.fn(),
    scanCurrentForm: vi.fn().mockResolvedValue(session),
    ...overrides,
  };
}

afterEach(() => {
  document.body.replaceChildren();
  vi.restoreAllMocks();
});

describe('Popup safe autofill workflow', () => {
  it('offers form scanning after health succeeds without reading the page or profile automatically', async () => {
    renderPopupRoot();
    const autofill = autofillDependencies();

    await initializePopup({
      getHealth: vi.fn().mockResolvedValue({ status: 'ok', service: 'jobpilot-api' }),
      autofill,
    });

    expect(screen.getByRole('button', { name: '扫描当前表单' })).toBeEnabled();
    expect(autofill.scanCurrentForm).not.toHaveBeenCalled();
    expect(autofill.getAutofillProfile).not.toHaveBeenCalled();
  });

  it('shows a masked preview with conservative default selections', async () => {
    const root = renderPopupRoot();
    const autofill = autofillDependencies();
    await initializePopup({
      getHealth: vi.fn().mockResolvedValue({ status: 'ok', service: 'jobpilot-api' }),
      autofill,
    });

    fireEvent.click(screen.getByRole('button', { name: '扫描当前表单' }));
    expect(root.dataset.state).toBe('scanning');
    await waitFor(() => expect(root.dataset.state).toBe('autofill-preview'));

    expect(autofill.scanCurrentForm).toHaveBeenCalledOnce();
    expect(autofill.getAutofillProfile).toHaveBeenCalledOnce();
    expect(screen.getByRole('checkbox', { name: '填写 姓名' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: '填写 专业方向' })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: '填写 专业方向' })).toBeEnabled();
    expect(screen.getByRole('checkbox', { name: '填写 期望薪资' })).toBeDisabled();
    expect(screen.getByRole('checkbox', { name: '填写 上传简历' })).toBeDisabled();
    expect(screen.getByRole('checkbox', { name: '填写 最喜欢的颜色' })).toBeDisabled();
    expect(screen.getByText('138****0000')).toBeVisible();
    expect(screen.getByText('ca***@example.test')).toBeVisible();
    expect(document.body.textContent).not.toContain('13800000000');
    expect(document.body.textContent).not.toContain('candidate@example.test');
    expect(autofill.fillCurrentForm).not.toHaveBeenCalled();
  });

  it('fills only the selections confirmed in Preview and blocks repeat clicks while filling', async () => {
    const root = renderPopupRoot();
    const fillResult = deferred<{
      status: 'COMPLETED';
      attempted: number;
      filled: number;
      failures: [];
    }>();
    const autofill = autofillDependencies({
      fillCurrentForm: vi.fn().mockReturnValue(fillResult.promise),
    });
    await initializePopup({
      getHealth: vi.fn().mockResolvedValue({ status: 'ok', service: 'jobpilot-api' }),
      autofill,
    });
    fireEvent.click(screen.getByRole('button', { name: '扫描当前表单' }));
    await waitFor(() => expect(root.dataset.state).toBe('autofill-preview'));

    fireEvent.click(screen.getByRole('checkbox', { name: '填写 姓名' }));
    fireEvent.click(screen.getByRole('checkbox', { name: '填写 专业方向' }));
    fireEvent.click(screen.getByRole('button', { name: '填写已确认字段' }));

    expect(root.dataset.state).toBe('filling');
    expect(root).toHaveAttribute('aria-busy', 'true');
    expect(screen.queryByRole('button', { name: '填写已确认字段' })).not.toBeInTheDocument();
    expect(autofill.fillCurrentForm).toHaveBeenCalledOnce();
    const sentPlan = autofill.fillCurrentForm.mock.calls[0]![1] as FillPlanItem[];
    expect(sentPlan.find((item) => item.canonicalKey === 'name')?.selected).toBe(false);
    expect(sentPlan.find((item) => item.canonicalKey === 'major')?.selected).toBe(true);

    fillResult.resolve({ status: 'COMPLETED', attempted: 3, filled: 3, failures: [] });
    await waitFor(() => expect(root.dataset.state).toBe('autofill-completed'));
    expect(screen.getByText('已填写 3 个字段')).toBeVisible();
    expect(screen.getByText('请检查内容后，由你在招聘网站完成提交。')).toBeVisible();
  });

  it('directs an empty-profile user to the local Profile page without filling', async () => {
    const root = renderPopupRoot();
    const autofill = autofillDependencies({
      getAutofillProfile: vi.fn().mockResolvedValue({ profile: null }),
    });
    await initializePopup({
      getHealth: vi.fn().mockResolvedValue({ status: 'ok', service: 'jobpilot-api' }),
      autofill,
    });

    fireEvent.click(screen.getByRole('button', { name: '扫描当前表单' }));
    await waitFor(() => expect(root.dataset.state).toBe('autofill-no-profile'));
    expect(screen.getByText('请先在 JobPilot 中完善求职资料')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '打开求职资料' }));
    expect(autofill.openProfile).toHaveBeenCalledOnce();
    expect(autofill.fillCurrentForm).not.toHaveBeenCalled();
  });

  it('shows page-changed and sanitized scan failure states that can rescan', async () => {
    const root = renderPopupRoot();
    const autofill = autofillDependencies({
      scanCurrentForm: vi
        .fn()
        .mockRejectedValueOnce(new Error('private page detail'))
        .mockResolvedValueOnce(session),
      fillCurrentForm: vi.fn().mockResolvedValue({
        status: 'PAGE_CHANGED',
        attempted: 0,
        filled: 0,
        failures: [],
      }),
    });
    await initializePopup({
      getHealth: vi.fn().mockResolvedValue({ status: 'ok', service: 'jobpilot-api' }),
      autofill,
    });

    fireEvent.click(screen.getByRole('button', { name: '扫描当前表单' }));
    await waitFor(() => expect(root.dataset.state).toBe('autofill-scan-error'));
    expect(document.body.textContent).not.toContain('private page detail');
    fireEvent.click(screen.getByRole('button', { name: '重新扫描' }));
    await waitFor(() => expect(root.dataset.state).toBe('autofill-preview'));
    fireEvent.click(screen.getByRole('button', { name: '填写已确认字段' }));
    await waitFor(() => expect(root.dataset.state).toBe('autofill-page-changed'));
    expect(screen.getByText('标签页或页面地址已变化，请重新扫描。')).toBeVisible();
  });

  it('distinguishes a rerendered field from a changed tab or URL without exposing values', async () => {
    const root = renderPopupRoot();
    const autofill = autofillDependencies({
      fillCurrentForm: vi.fn().mockResolvedValue({
        status: 'PAGE_CHANGED',
        attempted: 1,
        filled: 0,
        failures: [{ fieldRef: 'id:name', code: 'STALE_FIELD' }],
      }),
    });
    await initializePopup({
      getHealth: vi.fn().mockResolvedValue({ status: 'ok', service: 'jobpilot-api' }),
      autofill,
    });

    fireEvent.click(screen.getByRole('button', { name: '扫描当前表单' }));
    await waitFor(() => expect(root.dataset.state).toBe('autofill-preview'));
    fireEvent.click(screen.getByRole('button', { name: '填写已确认字段' }));
    await waitFor(() => expect(root.dataset.state).toBe('autofill-page-changed'));

    expect(screen.getByText('目标字段结构已变化，请重新扫描。')).toBeVisible();
    expect(document.body.textContent).not.toContain('id:name');
  });

  it('distinguishes a missing target ref without exposing the ref or value', async () => {
    const root = renderPopupRoot();
    const autofill = autofillDependencies({
      fillCurrentForm: vi.fn().mockResolvedValue({
        status: 'PAGE_CHANGED',
        attempted: 1,
        filled: 0,
        failures: [{ fieldRef: 'id:name', code: 'MISSING_REF' }],
      }),
    });
    await initializePopup({
      getHealth: vi.fn().mockResolvedValue({ status: 'ok', service: 'jobpilot-api' }),
      autofill,
    });

    fireEvent.click(screen.getByRole('button', { name: '扫描当前表单' }));
    await waitFor(() => expect(root.dataset.state).toBe('autofill-preview'));
    fireEvent.click(screen.getByRole('button', { name: '填写已确认字段' }));
    await waitFor(() => expect(root.dataset.state).toBe('autofill-page-changed'));

    expect(screen.getByText('目标字段暂时不可用，请重新扫描。')).toBeVisible();
    expect(document.body.textContent).not.toContain('id:name');
  });
});
