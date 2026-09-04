import {
  captureBossJobFromPage,
  type BossCaptureResult,
} from './boss-adapter';

export async function captureCurrentBossJob(): Promise<BossCaptureResult> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.id === undefined || tab.url === undefined || !isBossPage(tab.url)) {
    return { status: 'unsupported' };
  }
  const results = await chrome.scripting.executeScript({
    func: captureBossJobFromPage,
    target: { tabId: tab.id },
  });
  const result = results[0]?.result;
  if (result === undefined) throw new Error('BOSS parser returned no result');
  return result;
}

function isBossPage(value: string): boolean {
  try {
    const url = new URL(value);
    return (
      ['http:', 'https:'].includes(url.protocol) &&
      url.hostname === 'www.zhipin.com' &&
      url.username === '' &&
      url.password === ''
    );
  } catch {
    return false;
  }
}
