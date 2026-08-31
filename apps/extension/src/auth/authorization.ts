import {
  AuthorizationResponseError,
  calculatePKCECodeChallenge,
  generateRandomCodeVerifier,
  generateRandomNonce,
  generateRandomState,
  validateAuthResponse,
} from 'oauth4webapi';

import type { ExtensionAuthConfig } from './config';
import { ExtensionAuthError } from './errors';

const AUTHORIZATION_ATTEMPT_LIFETIME_MS = 600_000;
const AUTHORIZATION_SCOPE = 'openid profile email offline_access';

export interface AuthorizationAttempt {
  version: 1;
  state: string;
  nonce: string;
  codeVerifier: string;
  redirectUri: string;
  createdAt: number;
  expiresAt: number;
}

export interface AuthorizationPrimitives {
  generateCodeVerifier(): string;
  generateState(): string;
  generateNonce(): string;
  calculateCodeChallenge(codeVerifier: string): Promise<string>;
}

export interface AuthorizationAttemptStore {
  saveAttempt(attempt: AuthorizationAttempt): Promise<void>;
  loadAttempt(): Promise<AuthorizationAttempt>;
  clearAttempt(): Promise<void>;
}

interface ChromeIdentityBoundary {
  getRedirectURL(): string;
  launchWebAuthFlow(details: chrome.identity.WebAuthFlowDetails): Promise<string | undefined>;
}

interface CreateAuthorizationRequestOptions {
  config: ExtensionAuthConfig;
  redirectUri: string;
  now: number;
  primitives: AuthorizationPrimitives;
}

interface InteractiveAuthorizationOptions {
  config: ExtensionAuthConfig;
  store: AuthorizationAttemptStore;
  identity: ChromeIdentityBoundary;
  clock?: () => number;
  primitives?: AuthorizationPrimitives;
}

export interface AuthorizationLaunchOptions {
  signal: AbortSignal;
}

export interface ValidatedAuthorizationCallback {
  parameters: URLSearchParams;
  attempt: AuthorizationAttempt;
}

export function createDefaultAuthorizationPrimitives(): AuthorizationPrimitives {
  return {
    generateCodeVerifier: generateRandomCodeVerifier,
    generateState: generateRandomState,
    generateNonce: generateRandomNonce,
    calculateCodeChallenge: calculateS256CodeChallenge,
  };
}

export function calculateS256CodeChallenge(codeVerifier: string): Promise<string> {
  return calculatePKCECodeChallenge(codeVerifier);
}

export async function createAuthorizationRequest(
  options: CreateAuthorizationRequestOptions,
): Promise<{ attempt: AuthorizationAttempt; authorizationUrl: URL }> {
  requireChromeRedirect(options.redirectUri);
  const codeVerifier = options.primitives.generateCodeVerifier();
  const state = options.primitives.generateState();
  const nonce = options.primitives.generateNonce();
  const codeChallenge = await options.primitives.calculateCodeChallenge(codeVerifier);
  const attempt: AuthorizationAttempt = {
    version: 1,
    state,
    nonce,
    codeVerifier,
    redirectUri: options.redirectUri,
    createdAt: options.now,
    expiresAt: options.now + AUTHORIZATION_ATTEMPT_LIFETIME_MS,
  };
  if (!isAuthorizationAttempt(attempt)) {
    throw new ExtensionAuthError('AUTH_TOKEN_EXCHANGE_FAILED');
  }

  const authorizationUrl = new URL(options.config.authorizationEndpoint);
  authorizationUrl.searchParams.set('audience', options.config.audience);
  authorizationUrl.searchParams.set('client_id', options.config.clientId);
  authorizationUrl.searchParams.set('code_challenge', codeChallenge);
  authorizationUrl.searchParams.set('code_challenge_method', 'S256');
  authorizationUrl.searchParams.set('nonce', nonce);
  authorizationUrl.searchParams.set('redirect_uri', options.redirectUri);
  authorizationUrl.searchParams.set('response_type', 'code');
  authorizationUrl.searchParams.set('scope', AUTHORIZATION_SCOPE);
  authorizationUrl.searchParams.set('state', state);
  return { attempt, authorizationUrl };
}

export function validateAuthorizationCallback(
  callbackUrl: string,
  attempt: AuthorizationAttempt,
  config: ExtensionAuthConfig,
  now: number,
): ValidatedAuthorizationCallback {
  if (!isAuthorizationAttempt(attempt)) {
    throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
  }
  if (!Number.isSafeInteger(now) || now < attempt.createdAt || now >= attempt.expiresAt) {
    throw new ExtensionAuthError('AUTH_ATTEMPT_EXPIRED');
  }

  let callback: URL;
  let expectedRedirect: URL;
  try {
    callback = new URL(callbackUrl);
    expectedRedirect = new URL(attempt.redirectUri);
  } catch {
    throw new ExtensionAuthError('AUTH_STATE_MISMATCH');
  }
  if (
    callback.origin !== expectedRedirect.origin ||
    callback.pathname !== expectedRedirect.pathname ||
    callback.username.length > 0 ||
    callback.password.length > 0 ||
    callback.hash.length > 0
  ) {
    throw new ExtensionAuthError('AUTH_STATE_MISMATCH');
  }

  if (callback.searchParams.has('access_token') || callback.searchParams.has('refresh_token')) {
    throw new ExtensionAuthError('AUTH_STATE_MISMATCH');
  }

  let parameters: URLSearchParams;
  try {
    parameters = validateAuthResponse(
      {
        issuer: config.issuer,
      },
      { client_id: config.clientId },
      callback.searchParams,
      attempt.state,
    );
  } catch (error) {
    if (error instanceof AuthorizationResponseError) {
      throw new ExtensionAuthError('AUTH_PROVIDER_ERROR');
    }
    throw new ExtensionAuthError('AUTH_STATE_MISMATCH');
  }

  const codes = parameters.getAll('code');
  if (
    codes.length !== 1 ||
    codes[0] === undefined ||
    codes[0].length === 0 ||
    codes[0] !== codes[0].trim()
  ) {
    throw new ExtensionAuthError('AUTH_TOKEN_EXCHANGE_FAILED');
  }
  return { parameters, attempt };
}

export function isAuthorizationAttempt(value: unknown): value is AuthorizationAttempt {
  if (!isRecord(value) || value.version !== 1) {
    return false;
  }
  return (
    isBoundedRandomValue(value.state) &&
    isBoundedRandomValue(value.nonce) &&
    typeof value.codeVerifier === 'string' &&
    /^[A-Za-z0-9._~-]{43,128}$/u.test(value.codeVerifier) &&
    isChromeRedirect(value.redirectUri) &&
    typeof value.createdAt === 'number' &&
    Number.isSafeInteger(value.createdAt) &&
    typeof value.expiresAt === 'number' &&
    Number.isSafeInteger(value.expiresAt) &&
    value.expiresAt > value.createdAt &&
    value.expiresAt - value.createdAt <= AUTHORIZATION_ATTEMPT_LIFETIME_MS
  );
}

export class InteractiveAuthorization {
  readonly #config: ExtensionAuthConfig;
  readonly #store: AuthorizationAttemptStore;
  readonly #identity: ChromeIdentityBoundary;
  readonly #clock: () => number;
  readonly #primitives: AuthorizationPrimitives;

  constructor(options: InteractiveAuthorizationOptions) {
    this.#config = options.config;
    this.#store = options.store;
    this.#identity = options.identity;
    this.#clock = options.clock ?? Date.now;
    this.#primitives = options.primitives ?? createDefaultAuthorizationPrimitives();
  }

  async launch(options: AuthorizationLaunchOptions): Promise<ValidatedAuthorizationCallback> {
    requireActiveAuthorization(options.signal);
    const created = await createAuthorizationRequest({
      config: this.#config,
      redirectUri: this.#identity.getRedirectURL(),
      now: this.#clock(),
      primitives: this.#primitives,
    });
    requireActiveAuthorization(options.signal);

    let attemptWriteStarted = false;
    try {
      attemptWriteStarted = true;
      await this.#store.saveAttempt(created.attempt);
      requireActiveAuthorization(options.signal);
      const callbackUrl = await this.#launchWebAuthFlow(created.authorizationUrl.toString());
      requireActiveAuthorization(options.signal);
      const storedAttempt = await this.#store.loadAttempt();
      requireActiveAuthorization(options.signal);
      return validateAuthorizationCallback(callbackUrl, storedAttempt, this.#config, this.#clock());
    } finally {
      if (attemptWriteStarted) {
        await this.#store.clearAttempt();
      }
    }
  }

  async #launchWebAuthFlow(authorizationUrl: string): Promise<string> {
    try {
      const callbackUrl = await this.#identity.launchWebAuthFlow({
        interactive: true,
        url: authorizationUrl,
      });
      if (callbackUrl === undefined) {
        throw new ExtensionAuthError('AUTH_CANCELLED');
      }
      return callbackUrl;
    } catch (error) {
      if (error instanceof ExtensionAuthError) {
        throw error;
      }
      throw new ExtensionAuthError('AUTH_CANCELLED');
    }
  }
}

function requireActiveAuthorization(signal: AbortSignal): void {
  if (signal.aborted) {
    throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
  }
}

function requireChromeRedirect(value: string): void {
  if (!isChromeRedirect(value)) {
    throw new ExtensionAuthError('AUTH_STATE_MISMATCH');
  }
}

function isChromeRedirect(value: unknown): value is string {
  if (typeof value !== 'string') {
    return false;
  }
  try {
    const parsed = new URL(value);
    return (
      parsed.protocol === 'https:' &&
      /^[a-p]{32}\.chromiumapp\.org$/u.test(parsed.hostname) &&
      parsed.port.length === 0 &&
      parsed.username.length === 0 &&
      parsed.password.length === 0 &&
      parsed.pathname === '/' &&
      parsed.search.length === 0 &&
      parsed.hash.length === 0
    );
  } catch {
    return false;
  }
}

function isBoundedRandomValue(value: unknown): value is string {
  return typeof value === 'string' && /^[A-Za-z0-9._~-]{32,128}$/u.test(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
