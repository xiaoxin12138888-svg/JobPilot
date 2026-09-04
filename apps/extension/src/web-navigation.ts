const JOBPILOT_WEB_URL = 'http://127.0.0.1:5173/';

export async function openJobPilotJob(jobId?: string): Promise<void> {
  const url = new URL(JOBPILOT_WEB_URL);
  if (jobId !== undefined) url.searchParams.set('jobId', jobId);
  await chrome.tabs.create({ url: url.toString() });
}

export async function openManualJobForm(): Promise<void> {
  const url = new URL(JOBPILOT_WEB_URL);
  url.searchParams.set('view', 'create');
  await chrome.tabs.create({ url: url.toString() });
}
