import { isAuthorizationAttempt, type AuthorizationAttempt } from './authorization';
import { ExtensionAuthError } from './errors';

const AUTH_ATTEMPT_KEY = 'jobpilot.auth.attempt';
const TRUSTED_CONTEXTS = { accessLevel: 'TRUSTED_CONTEXTS' } as const;

export interface StorageArea {
  setAccessLevel(options: typeof TRUSTED_CONTEXTS): Promise<void>;
  get(key: string): Promise<Record<string, unknown>>;
  set(items: Record<string, unknown>): Promise<void>;
  remove(key: string): Promise<void>;
}

interface ChromeAuthStorageOptions {
  local: StorageArea;
  session: StorageArea;
}

export class ChromeAuthStorage {
  readonly #local: StorageArea;
  readonly #session: StorageArea;
  #trustedAccess: Promise<void> | undefined;

  constructor(options: ChromeAuthStorageOptions) {
    this.#local = options.local;
    this.#session = options.session;
  }

  async saveAttempt(attempt: AuthorizationAttempt): Promise<void> {
    if (!isAuthorizationAttempt(attempt)) {
      throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
    }
    await this.#withTrustedAccess(() => this.#session.set({ [AUTH_ATTEMPT_KEY]: attempt }));
  }

  async loadAttempt(): Promise<AuthorizationAttempt> {
    const stored = await this.#withTrustedAccess(() => this.#session.get(AUTH_ATTEMPT_KEY));
    const attempt = stored[AUTH_ATTEMPT_KEY];
    if (isAuthorizationAttempt(attempt)) {
      return attempt;
    }
    if (attempt !== undefined) {
      await this.#withTrustedAccess(() => this.#session.remove(AUTH_ATTEMPT_KEY));
    }
    throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
  }

  async clearAttempt(): Promise<void> {
    await this.#withTrustedAccess(() => this.#session.remove(AUTH_ATTEMPT_KEY));
  }

  async #withTrustedAccess<T>(operation: () => Promise<T>): Promise<T> {
    try {
      await this.#ensureTrustedAccess();
      return await operation();
    } catch (error) {
      if (error instanceof ExtensionAuthError) {
        throw error;
      }
      throw new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE');
    }
  }

  #ensureTrustedAccess(): Promise<void> {
    this.#trustedAccess ??= Promise.all([
      this.#local.setAccessLevel(TRUSTED_CONTEXTS),
      this.#session.setAccessLevel(TRUSTED_CONTEXTS),
    ]).then(() => undefined);
    return this.#trustedAccess;
  }
}
