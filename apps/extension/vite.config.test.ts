// @vitest-environment node

import { describe, expect, it } from 'vitest';

import { createExtensionViteConfig } from './vite.config';

describe('createExtensionViteConfig', () => {
  it('builds only the Popup for the declared minimum Chrome version', () => {
    const config = createExtensionViteConfig({ command: 'build', environment: {} });

    expect(config.build?.target).toBe('chrome106');
    expect(config.build?.modulePreload).toBe(false);
    expect(config.build?.rollupOptions?.input).toEqual({
      popup: expect.stringMatching(/[\\/]apps[\\/]extension[\\/]popup\.html$/u),
    });
    expect(config.build?.rollupOptions?.input).not.toHaveProperty('background');
  });
});
