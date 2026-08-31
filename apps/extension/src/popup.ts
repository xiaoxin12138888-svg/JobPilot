import type { ApiHealthResponse } from '@jobpilot/api-client';

interface PopupDependencies {
  getHealth(): Promise<ApiHealthResponse>;
}

type PopupState = 'checking' | 'available' | 'unavailable';

function getPopupRoot(): HTMLElement {
  const root = document.getElementById('popup-content');
  if (root === null) {
    throw new Error('Extension popup root was not found');
  }
  return root;
}

export async function initializePopup(dependencies: PopupDependencies): Promise<void> {
  const root = getPopupRoot();
  let requestInFlight = false;

  async function checkHealth(): Promise<void> {
    if (requestInFlight) {
      return;
    }
    requestInFlight = true;
    renderPopup(root, 'checking', checkHealth);
    try {
      await dependencies.getHealth();
      renderPopup(root, 'available', checkHealth);
    } catch {
      renderPopup(root, 'unavailable', checkHealth);
    } finally {
      requestInFlight = false;
    }
  }

  await checkHealth();
}

function renderPopup(root: HTMLElement, state: PopupState, retry: () => Promise<void>): void {
  root.dataset.state = state;
  root.setAttribute('aria-busy', state === 'checking' ? 'true' : 'false');

  const panel = document.createElement('div');
  panel.className = `health-state ${state}`;

  if (state === 'checking') {
    panel.append(
      statusText('正在检查本机 JobPilot…', 'status-title'),
      statusText('正在连接本机服务。', 'status-copy'),
    );
  } else if (state === 'available') {
    panel.append(
      statusText('本机 JobPilot 可用', 'status-title'),
      statusText('服务正在运行，可以使用本地工作台。', 'status-copy'),
    );
  } else {
    panel.append(
      statusText('本机 JobPilot 不可用', 'status-title'),
      statusText('请确认本机服务已启动，然后重试。', 'status-copy', 'alert'),
      retryButton(retry),
    );
  }

  root.replaceChildren(panel);
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

function retryButton(retry: () => Promise<void>): HTMLButtonElement {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'retry-button';
  button.textContent = '重试';
  button.addEventListener('click', () => {
    void retry();
  });
  return button;
}
