import { isAuthorizationAttempt, type AuthorizationAttempt } from './authorization';
import {
  areStorableCredentials,
  isCommittedReadyRecord,
  isGeneration,
  isRefreshInProgressRecord,
  isSafeTimestamp,
  isStoredAccessCredential,
  type ReadyRefreshRecord,
  type RefreshInProgressRecord,
  type StoredAccessCredential,
} from './credential-records';
import { ExtensionAuthError } from './errors';
import type { ExchangedProviderCredentials } from './provider-protocol';

const AUTH_ATTEMPT_KEY = 'jobpilot.auth.attempt';
const REFRESH_CREDENTIAL_KEY = 'jobpilot.auth.refresh';
const ACCESS_CREDENTIAL_KEY = 'jobpilot.auth.access';
const TRUSTED_CONTEXTS = { accessLevel: 'TRUSTED_CONTEXTS' } as const;

export interface AccessCredential {
  accessToken: string;
  accessTokenExpiresAt: number;
}

export type RestoredCredentialState =
  { status: 'signed_out' } | { status: 'ready'; access: AccessCredential | null };

export interface RefreshGrant {
  generation: number;
  refreshToken: string;
}

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
  #credentialOperationQueue: Promise<void> = Promise.resolve();
  #activeRefreshGeneration: number | undefined;

  constructor(options: ChromeAuthStorageOptions) {
    this.#local = options.local;
    this.#session = options.session;
  }

  async ensureTrustedAccess(): Promise<void> {
    await this.#withTrustedAccess(async () => undefined);
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

  async saveInitialCredentials(
    credentials: ExchangedProviderCredentials,
    now: number,
  ): Promise<void> {
    await this.#withTrustedAccess(() =>
      this.#serializeCredentialOperation(async () => {
        this.#activeRefreshGeneration = undefined;
        await this.#failClosedCredentialOperation(() =>
          this.#commitCredentials(1, credentials, now),
        );
      }),
    );
  }

  async restoreCredentials(): Promise<RestoredCredentialState> {
    return this.#withTrustedAccess(() =>
      this.#serializeCredentialOperation(() => {
        if (this.#activeRefreshGeneration !== undefined) {
          throw new ExtensionAuthError('AUTH_REFRESH_FAILED');
        }
        return this.#failClosedCredentialOperation(async () => {
          const [localState, sessionState] = await Promise.all([
            this.#local.get(REFRESH_CREDENTIAL_KEY),
            this.#session.get(ACCESS_CREDENTIAL_KEY),
          ]);
          const refreshRecord = localState[REFRESH_CREDENTIAL_KEY];
          const accessRecord = sessionState[ACCESS_CREDENTIAL_KEY];

          if (refreshRecord === undefined && accessRecord === undefined) {
            return { status: 'signed_out' };
          }
          if (!isCommittedReadyRecord(refreshRecord)) {
            throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
          }
          if (accessRecord === undefined) {
            return { status: 'ready', access: null };
          }
          if (
            !isStoredAccessCredential(accessRecord) ||
            accessRecord.generation !== refreshRecord.generation
          ) {
            throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
          }
          return {
            status: 'ready',
            access: {
              accessToken: accessRecord.accessToken,
              accessTokenExpiresAt: accessRecord.accessTokenExpiresAt,
            },
          };
        });
      }),
    );
  }

  async beginRefresh(now: number): Promise<RefreshGrant> {
    return this.#withTrustedAccess(() =>
      this.#serializeCredentialOperation(async () => {
        if (this.#activeRefreshGeneration !== undefined) {
          throw new ExtensionAuthError('AUTH_REFRESH_FAILED');
        }
        const grant = await this.#failClosedCredentialOperation(async () => {
          if (!isSafeTimestamp(now)) {
            throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
          }
          const [localState, sessionState] = await Promise.all([
            this.#local.get(REFRESH_CREDENTIAL_KEY),
            this.#session.get(ACCESS_CREDENTIAL_KEY),
          ]);
          const readyRecord = localState[REFRESH_CREDENTIAL_KEY];
          const accessRecord = sessionState[ACCESS_CREDENTIAL_KEY];
          if (
            !isCommittedReadyRecord(readyRecord) ||
            readyRecord.generation >= Number.MAX_SAFE_INTEGER
          ) {
            throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
          }
          if (
            accessRecord !== undefined &&
            (!isStoredAccessCredential(accessRecord) ||
              accessRecord.generation !== readyRecord.generation)
          ) {
            throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
          }

          const nextGrant: RefreshGrant = {
            generation: readyRecord.generation + 1,
            refreshToken: readyRecord.refreshToken,
          };
          const inProgress: RefreshInProgressRecord = {
            version: 1,
            status: 'refresh_in_progress',
            generation: nextGrant.generation,
            startedAt: now,
          };
          await this.#local.set({ [REFRESH_CREDENTIAL_KEY]: inProgress });
          await this.#session.remove(ACCESS_CREDENTIAL_KEY);
          return nextGrant;
        });
        this.#activeRefreshGeneration = grant.generation;
        return grant;
      }),
    );
  }

  async saveRefreshedCredentials(
    generation: number,
    credentials: ExchangedProviderCredentials,
    now: number,
  ): Promise<void> {
    await this.#withTrustedAccess(() =>
      this.#serializeCredentialOperation(async () => {
        if (this.#activeRefreshGeneration !== generation) {
          throw new ExtensionAuthError('AUTH_REFRESH_FAILED');
        }
        try {
          await this.#failClosedCredentialOperation(async () => {
            const stored = await this.#local.get(REFRESH_CREDENTIAL_KEY);
            const inProgress = stored[REFRESH_CREDENTIAL_KEY];
            if (!isRefreshInProgressRecord(inProgress) || inProgress.generation !== generation) {
              throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
            }
            await this.#commitCredentials(generation, credentials, now);
          });
        } finally {
          this.#activeRefreshGeneration = undefined;
        }
      }),
    );
  }

  async clearCredentials(): Promise<void> {
    await this.#withTrustedAccess(() =>
      this.#serializeCredentialOperation(async () => {
        try {
          const results = await Promise.allSettled([
            this.#local.remove(REFRESH_CREDENTIAL_KEY),
            this.#session.remove(ACCESS_CREDENTIAL_KEY),
          ]);
          if (results.some((result) => result.status === 'rejected')) {
            throw new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE');
          }
        } finally {
          this.#activeRefreshGeneration = undefined;
        }
      }),
    );
  }

  async #commitCredentials(
    generation: number,
    credentials: ExchangedProviderCredentials,
    now: number,
  ): Promise<void> {
    if (!isGeneration(generation) || !areStorableCredentials(credentials, now)) {
      throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
    }
    const pendingRefresh: ReadyRefreshRecord = {
      version: 1,
      status: 'ready',
      generation,
      accessState: 'pending',
      refreshToken: credentials.refreshToken,
    };
    const accessCredential: StoredAccessCredential = {
      version: 1,
      generation,
      accessToken: credentials.accessToken,
      accessTokenExpiresAt: credentials.accessTokenExpiresAt,
      storedAt: now,
    };
    const committedRefresh: ReadyRefreshRecord = {
      ...pendingRefresh,
      accessState: 'committed',
    };

    await this.#local.set({ [REFRESH_CREDENTIAL_KEY]: pendingRefresh });
    await this.#session.set({ [ACCESS_CREDENTIAL_KEY]: accessCredential });
    await this.#local.set({ [REFRESH_CREDENTIAL_KEY]: committedRefresh });
  }

  #serializeCredentialOperation<T>(operation: () => Promise<T>): Promise<T> {
    const result = this.#credentialOperationQueue.then(operation, operation);
    this.#credentialOperationQueue = result.then(
      () => undefined,
      () => undefined,
    );
    return result;
  }

  async #failClosedCredentialOperation<T>(operation: () => Promise<T>): Promise<T> {
    try {
      return await operation();
    } catch (error) {
      const cleared = await this.#clearCredentialRecordsBestEffort();
      if (!cleared) {
        throw new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE');
      }
      if (error instanceof ExtensionAuthError) {
        throw error;
      }
      throw new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE');
    }
  }

  async #clearCredentialRecordsBestEffort(): Promise<boolean> {
    const results = await Promise.allSettled([
      this.#local.remove(REFRESH_CREDENTIAL_KEY),
      this.#session.remove(ACCESS_CREDENTIAL_KEY),
    ]);
    return results.every((result) => result.status === 'fulfilled');
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
