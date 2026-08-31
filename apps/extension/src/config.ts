export const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';

export interface ExtensionConfig {
  apiBaseUrl: typeof DEFAULT_API_BASE_URL;
}

interface ExtensionEnvironment {
  VITE_API_BASE_URL?: unknown;
}

export function loadExtensionConfig(environment: ExtensionEnvironment): ExtensionConfig {
  const apiBaseUrl = environment.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;
  if (apiBaseUrl !== DEFAULT_API_BASE_URL) {
    throw new Error(`VITE_API_BASE_URL must be exactly ${DEFAULT_API_BASE_URL}`);
  }
  return { apiBaseUrl: DEFAULT_API_BASE_URL };
}
