import type { FillPlanItem, FillPlanStatus } from './autofill-types';
import type { FillExecutionResult } from './fill-executor';
import { actionButton, setRootState, statusText } from './popup-view';

const statusLabels: Readonly<Record<FillPlanStatus, string>> = {
  READY: '可填写',
  REVIEW_REQUIRED: '需确认',
  MANUAL: '手动填写',
  UNMAPPED: '未识别',
};

export function renderAutofillPreview(
  root: HTMLElement,
  plan: readonly FillPlanItem[],
  onSelectionChange: (fieldRef: string, selected: boolean) => void,
  onFill: () => Promise<void>,
  onRescan: () => Promise<void>,
): void {
  setRootState(root, 'autofill-preview');
  const panel = document.createElement('div');
  panel.className = 'popup-state autofill-preview';
  panel.append(
    statusText('确认填写内容', 'status-title'),
    statusText(planSummary(plan), 'status-copy'),
  );

  const fieldset = document.createElement('fieldset');
  fieldset.className = 'autofill-fields';
  const legend = document.createElement('legend');
  legend.textContent = '填写预览';
  fieldset.append(legend);

  const selectable: HTMLInputElement[] = [];
  for (const item of plan) {
    const row = document.createElement('label');
    row.className = 'autofill-row';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = item.selected;
    checkbox.disabled =
      item.proposedValue === null || (item.status !== 'READY' && item.status !== 'REVIEW_REQUIRED');
    checkbox.setAttribute('aria-label', `填写 ${item.pageLabel}`);
    if (!checkbox.disabled) selectable.push(checkbox);
    checkbox.addEventListener('change', () => {
      onSelectionChange(item.fieldRef, checkbox.checked);
      updateFillButton();
    });

    const details = document.createElement('span');
    details.className = 'autofill-field-details';
    const fieldName = document.createElement('span');
    fieldName.className = 'autofill-field-name';
    fieldName.textContent = item.pageLabel;
    const value = document.createElement('span');
    value.className = 'autofill-value';
    value.textContent = previewValue(item);
    details.append(fieldName, value);

    const status = document.createElement('span');
    status.className = `autofill-status status-${item.status.toLowerCase()}`;
    status.textContent = statusLabels[item.status];
    row.append(checkbox, details, status);
    fieldset.append(row);
  }

  const fillButton = actionButton('填写已确认字段', 'primary-button', () => void onFill());
  const updateFillButton = (): void => {
    fillButton.disabled = !selectable.some((checkbox) => checkbox.checked);
  };
  updateFillButton();
  const actions = document.createElement('div');
  actions.className = 'action-row';
  actions.append(
    fillButton,
    actionButton('重新扫描', 'secondary-button', () => void onRescan()),
  );
  panel.append(fieldset, actions);
  root.replaceChildren(panel);
}

export function renderAutofillNoProfile(
  root: HTMLElement,
  detected: number,
  openProfile: () => void,
  rescan: () => Promise<void>,
): void {
  renderAutofillActionState(
    root,
    'autofill-no-profile',
    '请先在 JobPilot 中完善求职资料',
    `已识别 ${detected} 个字段，但本机尚无可用于填写的资料。`,
    [
      actionButton('打开求职资料', 'primary-button', openProfile),
      actionButton('重新扫描', 'secondary-button', () => void rescan()),
    ],
  );
}

export function renderAutofillScanError(root: HTMLElement, rescan: () => Promise<void>): void {
  renderAutofillActionState(
    root,
    'autofill-scan-error',
    '未能读取当前表单',
    '请确认当前标签页是可访问的招聘申请表，然后重试。',
    [actionButton('重新扫描', 'primary-button', () => void rescan())],
    true,
  );
}

export function renderAutofillApiUnavailable(root: HTMLElement, rescan: () => Promise<void>): void {
  renderAutofillActionState(
    root,
    'autofill-unavailable',
    'JobPilot 本机服务未运行',
    '无法读取本机求职资料，请启动服务后重试。',
    [actionButton('重试', 'primary-button', () => void rescan())],
    true,
  );
}

export function renderAutofillUnsupported(root: HTMLElement, rescan: () => Promise<void>): void {
  renderAutofillActionState(
    root,
    'autofill-unsupported',
    '当前页面没有可填写字段',
    'JobPilot 没有修改页面。你可以切换到申请表后重新扫描。',
    [actionButton('重新扫描', 'primary-button', () => void rescan())],
  );
}

export function renderAutofillResult(
  root: HTMLElement,
  result: FillExecutionResult,
  rescan: () => Promise<void>,
  closePopup: () => void,
): void {
  if (result.status === 'PAGE_CHANGED') {
    renderAutofillActionState(
      root,
      'autofill-page-changed',
      '页面表单已变化，请重新扫描。',
      '为避免填错位置，本次没有继续填写失效字段。',
      [actionButton('重新扫描', 'primary-button', () => void rescan())],
      true,
    );
    return;
  }
  const completed = result.status === 'COMPLETED';
  renderAutofillActionState(
    root,
    completed ? 'autofill-completed' : 'autofill-partial',
    completed
      ? `已填写 ${result.filled} 个字段`
      : `已填写 ${result.filled}/${result.attempted} 个字段`,
    '请检查内容后，由你在招聘网站完成提交。',
    [
      actionButton('重新扫描', 'primary-button', () => void rescan()),
      actionButton('继续检查页面', 'secondary-button', closePopup),
    ],
    !completed,
  );
}

export function renderAutofillFillError(root: HTMLElement, rescan: () => Promise<void>): void {
  renderAutofillActionState(
    root,
    'autofill-partial',
    '未能确认填写结果',
    '页面没有被自动提交。请重新扫描后再试。',
    [actionButton('重新扫描', 'primary-button', () => void rescan())],
    true,
  );
}

function previewValue(item: FillPlanItem): string {
  if (item.proposedValue === null) return '—';
  if (item.canonicalKey === 'phone') return maskPhone(item.proposedValue);
  if (item.canonicalKey === 'email') return maskEmail(item.proposedValue);
  return item.proposedValue;
}

function maskPhone(value: string): string {
  if (value.length < 7) return '***';
  return `${value.slice(0, 3)}****${value.slice(-4)}`;
}

function maskEmail(value: string): string {
  const separator = value.indexOf('@');
  if (separator < 1) return '***';
  return `${value.slice(0, Math.min(2, separator))}***${value.slice(separator)}`;
}

function planSummary(plan: readonly FillPlanItem[]): string {
  const count = (status: FillPlanStatus): number =>
    plan.filter((item) => item.status === status).length;
  return `${plan.length} 个字段：可填写 ${count('READY')} · 需确认 ${count(
    'REVIEW_REQUIRED',
  )} · 手动填写 ${count('MANUAL')} · 未识别 ${count('UNMAPPED')}`;
}

function renderAutofillActionState(
  root: HTMLElement,
  state: Parameters<typeof setRootState>[1],
  title: string,
  copy: string,
  actions: HTMLButtonElement[],
  alert = false,
): void {
  setRootState(root, state);
  const panel = document.createElement('div');
  panel.className = `popup-state ${state}`;
  panel.append(
    statusText(title, 'status-title'),
    statusText(copy, 'status-copy', alert ? 'alert' : undefined),
  );
  const actionRow = document.createElement('div');
  actionRow.className = 'action-row';
  actionRow.append(...actions);
  panel.append(actionRow);
  root.replaceChildren(panel);
}
