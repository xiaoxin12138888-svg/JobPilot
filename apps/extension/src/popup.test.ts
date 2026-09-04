import { fireEvent, screen, waitFor } from '@testing-library/dom';
import { ApiRequestError } from '@jobpilot/api-client';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { initializePopup } from './popup';

const healthyResponse = { status: 'ok', service: 'jobpilot-api' } as const;
const capturedJob = {
  draft: {
    company: '示例科技',
    description: '负责本地产品体验。',
    location: '上海',
    salaryText: '20-30K',
    source: 'boss',
    sourceUrl: 'https://www.zhipin.com/job_detail/example.html',
    title: '产品经理',
  },
  warnings: ['请确认工作地点'],
} as const;
const savedJob = {
  ...capturedJob.draft,
  id: 'job-local-1',
  location: '杭州',
  notes: null,
  createdAt: '2026-09-03T08:00:00Z',
  updatedAt: '2026-09-03T08:00:00Z',
} as const;

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

function captureDependencies(overrides: Record<string, unknown> = {}) {
  return {
    captureCurrentJob: vi.fn().mockResolvedValue(capturedJob),
    closePopup: vi.fn(),
    createJob: vi.fn().mockResolvedValue(savedJob),
    openJobPilot: vi.fn(),
    openManualFallback: vi.fn(),
    ...overrides,
  };
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

  it('offers capture after health succeeds without reading the page automatically', async () => {
    renderPopupRoot();
    const capture = captureDependencies();

    await initializePopup({
      getHealth: vi.fn().mockResolvedValue(healthyResponse),
      capture,
    });

    expect(screen.getByText('可以读取当前岗位')).toBeVisible();
    expect(screen.getByRole('button', { name: '读取当前岗位' })).toBeEnabled();
    expect(capture.captureCurrentJob).not.toHaveBeenCalled();
  });

  it('shows parsing and then an editable preview with warnings', async () => {
    const root = renderPopupRoot();
    const captureResult = deferred<typeof capturedJob>();
    const capture = captureDependencies({
      captureCurrentJob: vi.fn().mockReturnValue(captureResult.promise),
    });
    await initializePopup({
      getHealth: vi.fn().mockResolvedValue(healthyResponse),
      capture,
    });

    fireEvent.click(screen.getByRole('button', { name: '读取当前岗位' }));

    expect(root.dataset.state).toBe('parsing');
    expect(root).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByText('正在读取当前岗位…')).toBeVisible();

    captureResult.resolve(capturedJob);
    await waitFor(() => expect(root.dataset.state).toBe('preview'));

    expect(screen.getByRole('textbox', { name: '职位名称' })).toHaveValue('产品经理');
    expect(screen.getByRole('textbox', { name: '公司' })).toHaveValue('示例科技');
    expect(screen.getByRole('textbox', { name: '地点' })).toHaveValue('上海');
    expect(screen.getByRole('textbox', { name: '薪资' })).toHaveValue('20-30K');
    expect(screen.getByRole('textbox', { name: '岗位描述' })).toHaveValue('负责本地产品体验。');
    expect(screen.getByRole('textbox', { name: '职位名称' })).toHaveAttribute('maxlength', '200');
    expect(screen.getByRole('textbox', { name: '公司' })).toHaveAttribute('maxlength', '200');
    expect(screen.getByRole('textbox', { name: '地点' })).toHaveAttribute('maxlength', '300');
    expect(screen.getByRole('textbox', { name: '薪资' })).toHaveAttribute('maxlength', '300');
    expect(screen.getByRole('textbox', { name: '岗位描述' })).toHaveAttribute(
      'maxlength',
      '100000',
    );
    expect(screen.getByText('来源：BOSS直聘')).toBeVisible();
    expect(screen.getByText('请确认工作地点')).toBeVisible();
  });

  it('saves the edited preview and opens only the local Job detail', async () => {
    const root = renderPopupRoot();
    const saveResult = deferred<typeof savedJob>();
    const capture = captureDependencies({
      createJob: vi.fn().mockReturnValue(saveResult.promise),
    });
    await initializePopup({
      getHealth: vi.fn().mockResolvedValue(healthyResponse),
      capture,
    });
    fireEvent.click(screen.getByRole('button', { name: '读取当前岗位' }));
    await waitFor(() => expect(root.dataset.state).toBe('preview'));

    fireEvent.input(screen.getByRole('textbox', { name: '职位名称' }), {
      target: { value: '  高级产品经理  ' },
    });
    fireEvent.input(screen.getByRole('textbox', { name: '地点' }), {
      target: { value: '杭州' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存到 JobPilot' }));

    expect(root.dataset.state).toBe('saving');
    expect(root).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByText('正在保存到 JobPilot…')).toBeVisible();
    saveResult.resolve(savedJob);
    await waitFor(() => expect(root.dataset.state).toBe('saved'));
    expect(capture.createJob).toHaveBeenCalledWith({
      company: '示例科技',
      description: '负责本地产品体验。',
      location: '杭州',
      salaryText: '20-30K',
      source: 'boss',
      sourceUrl: 'https://www.zhipin.com/job_detail/example.html',
      title: '高级产品经理',
    });

    fireEvent.click(screen.getByRole('button', { name: '在 JobPilot 中查看' }));
    expect(capture.openJobPilot).toHaveBeenCalledWith('job-local-1');
    fireEvent.click(screen.getByRole('button', { name: '继续浏览' }));
    expect(capture.closePopup).toHaveBeenCalledOnce();
  });

  it('blocks saving until required fields are confirmed', async () => {
    const root = renderPopupRoot();
    const capture = captureDependencies();
    await initializePopup({
      getHealth: vi.fn().mockResolvedValue(healthyResponse),
      capture,
    });
    fireEvent.click(screen.getByRole('button', { name: '读取当前岗位' }));
    await waitFor(() => expect(root.dataset.state).toBe('preview'));
    fireEvent.input(screen.getByRole('textbox', { name: '职位名称' }), {
      target: { value: '   ' },
    });

    fireEvent.click(screen.getByRole('button', { name: '保存到 JobPilot' }));

    expect(root.dataset.state).toBe('preview');
    expect(screen.getByRole('alert')).toHaveTextContent('请确认职位名称和公司');
    expect(capture.createJob).not.toHaveBeenCalled();
  });

  it('shows unsupported pages without guessing and opens manual fallback on request', async () => {
    const root = renderPopupRoot();
    const capture = captureDependencies({
      captureCurrentJob: vi.fn().mockResolvedValue({ status: 'unsupported' }),
    });
    await initializePopup({
      getHealth: vi.fn().mockResolvedValue(healthyResponse),
      capture,
    });

    fireEvent.click(screen.getByRole('button', { name: '读取当前岗位' }));
    await waitFor(() => expect(root.dataset.state).toBe('unsupported'));

    expect(screen.getByText('请先打开一个具体的 BOSS 直聘岗位详情页')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '打开 JobPilot 手动添加' }));
    expect(capture.openManualFallback).toHaveBeenCalledOnce();
  });

  it('keeps parse errors bounded and allows capture retry', async () => {
    const root = renderPopupRoot();
    const capture = captureDependencies({
      captureCurrentJob: vi
        .fn()
        .mockRejectedValueOnce(new Error('private DOM detail'))
        .mockResolvedValueOnce(capturedJob),
    });
    await initializePopup({
      getHealth: vi.fn().mockResolvedValue(healthyResponse),
      capture,
    });

    fireEvent.click(screen.getByRole('button', { name: '读取当前岗位' }));
    await waitFor(() => expect(root.dataset.state).toBe('parse-error'));
    expect(screen.getByText('未能完整识别当前岗位')).toBeVisible();
    expect(document.body.textContent).not.toContain('private DOM detail');

    fireEvent.click(screen.getByRole('button', { name: '重新读取' }));
    await waitFor(() => expect(root.dataset.state).toBe('preview'));
    expect(capture.captureCurrentJob).toHaveBeenCalledTimes(2);
  });

  it('maps duplicate saves to the existing local Job', async () => {
    const root = renderPopupRoot();
    const capture = captureDependencies({
      createJob: vi.fn().mockRejectedValue(
        new ApiRequestError(409, {
          code: 'DUPLICATE_JOB_URL',
          message: '该岗位链接已经保存',
          requestId: 'req-local',
          resourceId: 'existing-job',
        }),
      ),
    });
    await initializePopup({
      getHealth: vi.fn().mockResolvedValue(healthyResponse),
      capture,
    });
    fireEvent.click(screen.getByRole('button', { name: '读取当前岗位' }));
    await waitFor(() => expect(root.dataset.state).toBe('preview'));

    fireEvent.click(screen.getByRole('button', { name: '保存到 JobPilot' }));

    await waitFor(() => expect(root.dataset.state).toBe('duplicate'));
    expect(screen.getByText('该岗位已保存')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '在 JobPilot 中查看' }));
    expect(capture.openJobPilot).toHaveBeenCalledWith('existing-job');
  });

  it('preserves the edited draft after save failure and retries', async () => {
    const root = renderPopupRoot();
    const createJob = vi
      .fn()
      .mockRejectedValueOnce(new Error('private API detail'))
      .mockResolvedValueOnce(savedJob);
    const capture = captureDependencies({ createJob });
    await initializePopup({
      getHealth: vi.fn().mockResolvedValue(healthyResponse),
      capture,
    });
    fireEvent.click(screen.getByRole('button', { name: '读取当前岗位' }));
    await waitFor(() => expect(root.dataset.state).toBe('preview'));
    fireEvent.input(screen.getByRole('textbox', { name: '地点' }), {
      target: { value: '杭州' },
    });

    fireEvent.click(screen.getByRole('button', { name: '保存到 JobPilot' }));
    await waitFor(() => expect(root.dataset.state).toBe('save-error'));
    expect(screen.getByText('保存失败，请确认本机服务后重试')).toBeVisible();
    expect(document.body.textContent).not.toContain('private API detail');

    fireEvent.click(screen.getByRole('button', { name: '重试保存' }));
    await waitFor(() => expect(root.dataset.state).toBe('saved'));
    expect(createJob).toHaveBeenLastCalledWith(expect.objectContaining({ location: '杭州' }));
  });
});
