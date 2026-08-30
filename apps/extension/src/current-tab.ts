export async function getCurrentTabUrl(): Promise<string | null> {
  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return activeTab?.url ?? null;
}
