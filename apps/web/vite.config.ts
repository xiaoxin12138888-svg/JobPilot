import { fileURLToPath } from 'node:url';

import { validateApiBaseUrl } from '@jobpilot/api-client';
import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';

const repositoryDirectory = fileURLToPath(new URL('../..', import.meta.url));

interface WebEnvironment {
  VITE_API_BASE_URL?: string;
}

export function validateWebEnvironment(environment: WebEnvironment): void {
  validateApiBaseUrl(environment.VITE_API_BASE_URL ?? '');
}

export default defineConfig(({ mode }) => {
  validateWebEnvironment(loadEnv(mode, repositoryDirectory, 'VITE_'));

  return {
    envDir: repositoryDirectory,
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test-setup.ts',
    },
  };
});
