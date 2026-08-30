import type { ApiClient } from '@jobpilot/api-client';

interface PopupDependencies {
  getCurrentTabUrl(): Promise<string | null>;
  getHealth: ApiClient['getHealth'];
}

function getStatusElement(id: string): HTMLElement {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Extension popup element was not found: ${id}`);
  }
  return element;
}

export async function initializePopup(dependencies: PopupDependencies): Promise<void> {
  const currentTabElement = getStatusElement('current-tab-url');
  const apiStatusElement = getStatusElement('api-status');

  const [currentTabResult, healthResult] = await Promise.allSettled([
    dependencies.getCurrentTabUrl(),
    dependencies.getHealth(),
  ]);

  const currentTabUrl = currentTabResult.status === 'fulfilled' ? currentTabResult.value : null;
  currentTabElement.textContent = `Current tab URL: ${currentTabUrl ?? 'Unavailable'}`;

  const isConnected = healthResult.status === 'fulfilled';
  apiStatusElement.textContent = `API connection status: ${isConnected ? 'Connected' : 'Unavailable'}`;
  apiStatusElement.dataset.status = isConnected ? 'connected' : 'unavailable';
}
