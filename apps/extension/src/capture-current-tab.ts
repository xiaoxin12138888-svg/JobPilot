import { captureBossJobFromPage } from './boss-adapter';
import type { JobCapturePlatform, JobCaptureResult } from './job-capture';
import { captureNowcoderJobFromPage } from './nowcoder-adapter';

export async function captureCurrentJob(): Promise<JobCaptureResult> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.id === undefined || tab.url === undefined) {
    return { status: 'unsupported' };
  }
  const platform = platformForUrl(tab.url);
  if (platform === undefined) return { status: 'unsupported' };
  const parser = platform === 'boss' ? captureBossJobFromPage : captureNowcoderJobFromPage;
  const results = await chrome.scripting.executeScript({
    func: parser,
    target: { tabId: tab.id },
  });
  const result = results[0]?.result;
  if (result === undefined) throw new Error('Job parser returned no result');
  if ('status' in result) return { ...result, platform };
  return result;
}

function platformForUrl(value: string): JobCapturePlatform | undefined {
  try {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol) || url.username !== '' || url.password !== '') {
      return undefined;
    }
    if (url.hostname === 'www.zhipin.com') return 'boss';
    if (url.hostname === 'www.nowcoder.com') return 'nowcoder';
    return undefined;
  } catch {
    return undefined;
  }
}
