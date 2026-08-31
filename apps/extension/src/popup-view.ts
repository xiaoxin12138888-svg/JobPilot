import type { PopupSafeUser } from './popup-messages';

export type PopupOperation = 'restore' | 'sign-in' | 'sign-out';

export type PopupViewState =
  | { status: 'signed-out' }
  | { status: 'authenticating'; operation: PopupOperation }
  | { status: 'signed-in'; user: PopupSafeUser; isOpening: boolean; openFailed: boolean }
  | { status: 'error'; retry: PopupOperation }
  | { status: 'revoke-unconfirmed' };

export interface PopupActions {
  openWebApp(): Promise<void>;
  restore(): Promise<void>;
  signIn(): Promise<void>;
  signOut(): Promise<void>;
}

export function renderPopup(root: HTMLElement, state: PopupViewState, actions: PopupActions): void {
  root.dataset.state = state.status;
  root.setAttribute('aria-busy', state.status === 'authenticating' ? 'true' : 'false');

  const panel = document.createElement('div');
  panel.className = 'auth-state';
  switch (state.status) {
    case 'signed-out':
      panel.append(
        statusText('尚未登录', 'status-title'),
        statusText('登录后即可连接你的 JobPilot 账户。', 'status-copy'),
        actionButton('登录 JobPilot', actions.signIn),
      );
      break;
    case 'authenticating':
      panel.append(statusText(operationLabel(state.operation), 'status-title busy-status'));
      break;
    case 'signed-in':
      renderSignedIn(panel, state, actions);
      break;
    case 'error':
      renderError(panel, state.retry, actions);
      break;
    case 'revoke-unconfirmed':
      panel.append(
        statusText(
          '已在本机退出，但远端授权状态未确认。恢复网络后请检查账户安全。',
          'notice warning',
        ),
        actionButton('登录 JobPilot', actions.signIn),
      );
      break;
  }
  root.replaceChildren(panel);
}

function renderSignedIn(
  panel: HTMLElement,
  state: Extract<PopupViewState, { status: 'signed-in' }>,
  actions: PopupActions,
): void {
  const account = document.createElement('div');
  account.className = 'account-summary';

  const displayName = state.user.displayName?.trim() || state.user.email;
  account.append(statusText(displayName, 'account-name'));
  if (displayName !== state.user.email) {
    account.append(statusText(state.user.email, 'account-email'));
  }

  const identity = document.createElement('dl');
  identity.className = 'identity-list';
  const label = document.createElement('dt');
  label.textContent = 'User ID';
  const value = document.createElement('dd');
  value.textContent = state.user.id;
  identity.append(label, value);

  const actionsRow = document.createElement('div');
  actionsRow.className = 'action-row';
  actionsRow.append(
    actionButton(state.isOpening ? '正在打开...' : '打开 JobPilot', actions.openWebApp, {
      disabled: state.isOpening,
    }),
    actionButton('退出', actions.signOut, { disabled: state.isOpening, secondary: true }),
  );

  panel.append(statusText('✓ 已登录', 'status-title success'), account, identity, actionsRow);
  if (state.openFailed) {
    panel.append(statusText('暂时无法打开 JobPilot，请重试。', 'notice error', 'alert'));
  }
}

function renderError(panel: HTMLElement, retry: PopupOperation, actions: PopupActions): void {
  const messages: Record<PopupOperation, string> = {
    restore: '暂时无法读取登录状态，请重试。',
    'sign-in': '登录暂时不可用，请重试。',
    'sign-out': '退出未完成，请重试。',
  };
  const labels: Record<PopupOperation, string> = {
    restore: '重试',
    'sign-in': '重新登录',
    'sign-out': '重试退出',
  };
  const retryActions: Record<PopupOperation, () => Promise<void>> = {
    restore: actions.restore,
    'sign-in': actions.signIn,
    'sign-out': actions.signOut,
  };
  panel.append(
    statusText(messages[retry], 'notice error', 'alert'),
    actionButton(labels[retry], retryActions[retry]),
  );
}

function operationLabel(operation: PopupOperation): string {
  switch (operation) {
    case 'restore':
      return '正在检查登录状态...';
    case 'sign-in':
      return '正在登录...';
    case 'sign-out':
      return '正在退出...';
  }
}

function statusText(text: string, className: string, role?: string): HTMLParagraphElement {
  const paragraph = document.createElement('p');
  paragraph.className = className;
  paragraph.textContent = text;
  if (role !== undefined) {
    paragraph.setAttribute('role', role);
  }
  return paragraph;
}

function actionButton(
  label: string,
  action: () => Promise<void>,
  options: { disabled?: boolean; secondary?: boolean } = {},
): HTMLButtonElement {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = options.secondary === true ? 'button secondary' : 'button primary';
  button.disabled = options.disabled === true;
  button.textContent = label;
  button.addEventListener('click', () => {
    void action();
  });
  return button;
}
