import { fileURLToPath } from 'node:url';

import { validateApiBaseUrl } from '@jobpilot/api-client';
import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';

const repositoryDirectory = fileURLToPath(new URL('../..', import.meta.url));
const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';

export const WEB_DEV_HOST = '127.0.0.1';

interface WebEnvironment {
  VITE_API_BASE_URL?: string;
}

export function validateWebEnvironment(environment: WebEnvironment): void {
  resolveApiBaseUrl(environment);
}

export function createWebConfig(environment: WebEnvironment) {
  const apiBaseUrl = resolveApiBaseUrl(environment);

  return {
    define: {
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify(apiBaseUrl),
    },
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

function resolveApiBaseUrl(environment: WebEnvironment): string {
  const apiBaseUrl = environment.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;
  validateApiBaseUrl(apiBaseUrl);
  return apiBaseUrl;
}

export default defineConfig(({ mode }) =>
  createWebConfig(loadEnv(mode, repositoryDirectory, 'VITE_')),
);
