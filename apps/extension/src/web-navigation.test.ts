import { afterEach, describe, expect, it, vi } from 'vitest';

import { openJobPilotJob, openManualJobForm } from './web-navigation';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('Extension Web navigation', () => {
  it('opens a Job detail using only the local Job ID', async () => {
    const create = vi.fn().mockResolvedValue({});
    vi.stubGlobal('chrome', { tabs: { create } });

    await openJobPilotJob('local/job?private=ignored-as-data');

    expect(create).toHaveBeenCalledWith({
      url: 'http://127.0.0.1:5173/?jobId=local%2Fjob%3Fprivate%3Dignored-as-data',
    });
  });

  it('opens the manual-create fallback without captured page data', async () => {
    const create = vi.fn().mockResolvedValue({});
    vi.stubGlobal('chrome', { tabs: { create } });

    await openManualJobForm();

    expect(create).toHaveBeenCalledWith({
      url: 'http://127.0.0.1:5173/?view=create',
    });
  });
});
