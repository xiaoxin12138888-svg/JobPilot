import { fileURLToPath } from 'node:url';

import { loadEnv, type Plugin, type UserConfig } from 'vite';
import { defineConfig } from 'vitest/config';

import { createManifest } from './manifest.ts';
import { loadExtensionConfig, type ExtensionConfig } from './src/config.ts';

const projectDirectory = fileURLToPath(new URL('.', import.meta.url));
const repositoryDirectory = fileURLToPath(new URL('../..', import.meta.url));

interface CreateExtensionViteConfigOptions {
  command: 'build' | 'serve';
  environment: Record<string, unknown>;
}

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

export function createExtensionViteConfig({
  command,
  environment,
}: CreateExtensionViteConfigOptions): UserConfig {
  const extensionConfig = loadExtensionConfig(environment);

  return {
    envDir: repositoryDirectory,
    plugins: command === 'build' ? [emitManifest(extensionConfig)] : [],
    build: {
      target: 'chrome106',
      modulePreload: false,
      outDir: fileURLToPath(new URL('./dist', import.meta.url)),
      emptyOutDir: true,
      rollupOptions: {
        input: {
          popup: fileURLToPath(new URL('./popup.html', import.meta.url)),
        },
      },
    },
    root: projectDirectory,
    test: {
      environment: 'jsdom',
      setupFiles: './src/test-setup.ts',
    },
  };
}

export default defineConfig(({ command, mode }) =>
  createExtensionViteConfig({
    command,
    environment: loadEnv(mode, repositoryDirectory, 'VITE_'),
  }),
);
