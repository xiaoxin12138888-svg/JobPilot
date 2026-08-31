import { fileURLToPath } from 'node:url';

import { validateApiBaseUrl } from '@jobpilot/api-client';
import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';

const repositoryDirectory = fileURLToPath(new URL('../..', import.meta.url));

export const WEB_DEV_HOST = '127.0.0.1';

interface WebEnvironment {
  VITE_API_BASE_URL?: string;
}

export function validateWebEnvironment(environment: WebEnvironment): void {
  validateApiBaseUrl(environment.VITE_API_BASE_URL ?? '');
}

export function createWebConfig(environment: WebEnvironment) {
  validateWebEnvironment(environment);

  return {
    envDir: repositoryDirectory,
    plugins: [react()],
    server: {
      host: WEB_DEV_HOST,
      port: 5173,
      strictPort: true,
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test-setup.ts',
    },
  };
}

export default defineConfig(({ mode }) =>
  createWebConfig(loadEnv(mode, repositoryDirectory, 'VITE_')),
);
