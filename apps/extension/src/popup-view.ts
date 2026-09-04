import type { JobCapturePlatform } from './job-capture';

export type PopupState =
  | 'checking'
  | 'available'
  | 'unavailable'
  | 'ready'
  | 'parsing'
  | 'preview'
  | 'saving'
  | 'saved'
  | 'duplicate'
  | 'unsupported'
  | 'parse-error'
  | 'save-error';

export function setRootState(root: HTMLElement, state: PopupState): void {
  root.dataset.state = state;
  root.setAttribute(
    'aria-busy',
    state === 'checking' || state === 'parsing' || state === 'saving' ? 'true' : 'false',
  );
}

export function renderStatus(
  root: HTMLElement,
  state: PopupState,
  title: string,
  copy: string,
): void {
  setRootState(root, state);
  const panel = document.createElement('div');
  panel.className = `popup-state ${state}`;
  panel.append(statusText(title, 'status-title'), statusText(copy, 'status-copy'));
  root.replaceChildren(panel);
}

export function renderReady(root: HTMLElement, onCapture: () => Promise<void>): void {
  renderActionState(
    root,
    'ready',
    '可以读取当前岗位',
    '请确认当前标签是一个具体的 BOSS 直聘或牛客招聘岗位详情页。',
    [actionButton('读取当前岗位', 'primary-button', () => void onCapture())],
  );
}

export function renderUnavailable(root: HTMLElement, retry: () => Promise<void>): void {
  renderActionState(
    root,
    'unavailable',
    '本机 JobPilot 不可用',
    '请确认本机服务已启动，然后重试。',
    [actionButton('重试', 'primary-button', () => void retry())],
    true,
  );
}

export function renderUnsupported(
  root: HTMLElement,
  platform: JobCapturePlatform | undefined,
  retry: () => Promise<void>,
  manualFallback: () => void,
): void {
  renderActionState(root, 'unsupported', unsupportedTitle(platform), '当前页面不会被读取或保存。', [
    actionButton('重新读取', 'primary-button', () => void retry()),
    actionButton('打开 JobPilot 手动添加', 'secondary-button', manualFallback),
  ]);
}

function unsupportedTitle(platform: JobCapturePlatform | undefined): string {
  if (platform === 'boss') return '请先打开一个具体的 BOSS 直聘岗位详情页';
  if (platform === 'nowcoder') return '请先打开一个具体的牛客招聘岗位详情页';
  return '请先打开一个具体的 BOSS 直聘或牛客招聘岗位详情页';
}

export function renderParseError(
  root: HTMLElement,
  retry: () => Promise<void>,
  manualFallback: () => void,
): void {
  renderActionState(
    root,
    'parse-error',
    '未能完整识别当前岗位',
    '页面可能已更新，请重试或改用手动添加。',
    [
      actionButton('重新读取', 'primary-button', () => void retry()),
      actionButton('打开 JobPilot 手动添加', 'secondary-button', manualFallback),
    ],
    true,
  );
}

export function renderSaved(root: HTMLElement, openJob: () => void, closePopup: () => void): void {
  renderActionState(root, 'saved', '已保存到 JobPilot', '岗位快照已写入本机工作台。', [
    actionButton('在 JobPilot 中查看', 'primary-button', openJob),
    actionButton('继续浏览', 'secondary-button', closePopup),
  ]);
}

export function renderDuplicate(root: HTMLElement, openJob: () => void): void {
  renderActionState(root, 'duplicate', '该岗位已保存', '不会创建重复岗位。', [
    actionButton('在 JobPilot 中查看', 'primary-button', openJob),
  ]);
}

export function renderSaveError(
  root: HTMLElement,
  retry: () => void,
  manualFallback: () => void,
): void {
  renderActionState(
    root,
    'save-error',
    '保存失败，请确认本机服务后重试',
    '已编辑的岗位信息会保留到本次 Popup 关闭。',
    [
      actionButton('重试保存', 'primary-button', retry),
      actionButton('打开 JobPilot 手动添加', 'secondary-button', manualFallback),
    ],
    true,
  );
}

function renderActionState(
  root: HTMLElement,
  state: PopupState,
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

export function statusText(text: string, className: string, role?: string): HTMLParagraphElement {
  const paragraph = document.createElement('p');
  paragraph.className = className;
  paragraph.textContent = text;
  if (role !== undefined) paragraph.setAttribute('role', role);
  return paragraph;
}

export function actionButton(
  text: string,
  className: string,
  action: () => void,
  type: 'button' | 'submit' = 'button',
): HTMLButtonElement {
  const button = document.createElement('button');
  button.type = type;
  button.className = className;
  button.textContent = text;
  if (type === 'button') button.addEventListener('click', action);
  return button;
}
