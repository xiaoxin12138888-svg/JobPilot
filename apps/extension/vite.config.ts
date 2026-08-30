import { fileURLToPath } from 'node:url';

import { loadEnv, type Plugin } from 'vite';
import { defineConfig } from 'vitest/config';

import { createManifest } from './manifest.ts';

const projectDirectory = fileURLToPath(new URL('.', import.meta.url));
const repositoryDirectory = fileURLToPath(new URL('../..', import.meta.url));

function emitManifest(apiBaseUrl: string): Plugin {
  const manifest = createManifest(apiBaseUrl);

  return {
    name: 'jobpilot-extension-manifest',
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: 'manifest.json',
        source: `${JSON.stringify(manifest, null, 2)}\n`,
      });
    },
  };
}

export default defineConfig(({ command, mode }) => {
  const environment = loadEnv(mode, repositoryDirectory, 'VITE_');

  return {
    envDir: repositoryDirectory,
    plugins: command === 'build' ? [emitManifest(environment.VITE_API_BASE_URL ?? '')] : [],
    build: {
      outDir: fileURLToPath(new URL('./dist', import.meta.url)),
      emptyOutDir: true,
      rollupOptions: {
        input: fileURLToPath(new URL('./popup.html', import.meta.url)),
      },
    },
    root: projectDirectory,
    test: {
      environment: 'jsdom',
      setupFiles: './src/test-setup.ts',
    },
  };
});
