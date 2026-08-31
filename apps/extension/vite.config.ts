import { fileURLToPath } from 'node:url';

import { loadEnv, type Plugin } from 'vite';
import { defineConfig } from 'vitest/config';

import { createManifest } from './manifest.ts';
import { loadExtensionConfig, type ExtensionConfig } from './src/auth/config.ts';

const projectDirectory = fileURLToPath(new URL('.', import.meta.url));
const repositoryDirectory = fileURLToPath(new URL('../..', import.meta.url));

function emitManifest(config: ExtensionConfig): Plugin {
  const manifest = createManifest(config);

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
  const plugins = command === 'build' ? [emitManifest(loadExtensionConfig(environment))] : [];

  return {
    envDir: repositoryDirectory,
    plugins,
    build: {
      outDir: fileURLToPath(new URL('./dist', import.meta.url)),
      emptyOutDir: true,
      rollupOptions: {
        input: {
          background: fileURLToPath(new URL('./src/background.ts', import.meta.url)),
          popup: fileURLToPath(new URL('./popup.html', import.meta.url)),
        },
        output: {
          entryFileNames: (chunk) =>
            chunk.name === 'background' ? 'background.js' : 'assets/[name]-[hash].js',
        },
      },
    },
    root: projectDirectory,
    test: {
      environment: 'jsdom',
      setupFiles: './src/test-setup.ts',
    },
  };
});
