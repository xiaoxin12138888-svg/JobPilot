import { validateApiBaseUrl } from '@jobpilot/api-client';

export interface ExtensionAuthConfig {
  issuer: string;
  authorizationEndpoint: string;
  tokenEndpoint: string;
  jwksUri: string;
  revocationEndpoint: string;
  audience: string;
  clientId: string;
}

export interface ExtensionConfig {
  apiBaseUrl: string;
  auth: ExtensionAuthConfig;
  webAppUrl: string;
}

type ExtensionEnvironment = Record<string, unknown>;

export function loadExtensionConfig(environment: ExtensionEnvironment): ExtensionConfig {
  const apiBaseUrl = requiredValue(environment, 'VITE_API_BASE_URL');
  const issuerValue = requiredValue(environment, 'VITE_AUTH_ISSUER');
  const issuer = fixedHttpsUrl('VITE_AUTH_ISSUER', issuerValue);
  if (issuer.pathname !== '/' || !issuerValue.endsWith('/')) {
    throw new Error('VITE_AUTH_ISSUER must use its canonical trailing slash');
  }

  const authorizationEndpoint = providerEndpoint(environment, 'VITE_AUTH_AUTHORIZE_URL', issuer);
  const tokenEndpoint = providerEndpoint(environment, 'VITE_AUTH_TOKEN_URL', issuer);
  const jwksUri = providerEndpoint(environment, 'VITE_AUTH_JWKS_URL', issuer);
  const revocationEndpoint = providerEndpoint(environment, 'VITE_AUTH_REVOKE_URL', issuer);
  const audience = requiredValue(environment, 'VITE_AUTH_AUDIENCE');
  const clientId = requiredValue(environment, 'VITE_AUTH_EXTENSION_CLIENT_ID');
  const webAppUrl = exactWebOrigin(requiredValue(environment, 'VITE_WEB_APP_URL'));

  return {
    apiBaseUrl: validateApiBaseUrl(apiBaseUrl).toString(),
    auth: {
      issuer: issuer.toString(),
      authorizationEndpoint,
      tokenEndpoint,
      jwksUri,
      revocationEndpoint,
      audience,
      clientId,
    },
    webAppUrl,
  };
}

function requiredValue(environment: ExtensionEnvironment, key: string): string {
  const value = environment[key];
  if (typeof value !== 'string' || value.length === 0) {
    throw new Error(`Missing Extension configuration: ${key}`);
  }
  if (value !== value.trim()) {
    throw new Error(`${key} must be a non-empty exact value`);
  }
  return value;
}

function providerEndpoint(environment: ExtensionEnvironment, key: string, issuer: URL): string {
  const endpoint = fixedHttpsUrl(key, requiredValue(environment, key));
  if (endpoint.origin !== issuer.origin) {
    throw new Error(`${key} must share the issuer origin`);
  }
  return endpoint.toString();
}

function fixedHttpsUrl(key: string, value: string): URL {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error(`${key} must be a fixed HTTPS URL`);
  }
  if (
    parsed.protocol !== 'https:' ||
    parsed.username.length > 0 ||
    parsed.password.length > 0 ||
    parsed.search.length > 0 ||
    parsed.hash.length > 0
  ) {
    throw new Error(`${key} must be a fixed HTTPS URL`);
  }
  return parsed;
}

function exactWebOrigin(value: string): string {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error('VITE_WEB_APP_URL must be an exact HTTP or HTTPS origin');
  }
  if (
    (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') ||
    parsed.username.length > 0 ||
    parsed.password.length > 0 ||
    parsed.pathname !== '/' ||
    parsed.search.length > 0 ||
    parsed.hash.length > 0
  ) {
    throw new Error('VITE_WEB_APP_URL must be an exact HTTP or HTTPS origin');
  }
  return parsed.toString();
}
