import { isAuthorizationAttempt, type AuthorizationAttempt } from './authorization';
import {
  areStorableCredentials,
  isCommittedReadyRecord,
  isGeneration,
  isLocallyClearedRefreshRecord,
  isRefreshInProgressRecord,
  isSafeTimestamp,
  isStoredAccessCredential,
  type LocallyClearedRefreshRecord,
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
const LOCALLY_CLEARED_REFRESH_RECORD: LocallyClearedRefreshRecord = {
  version: 1,
  status: 'locally_cleared',
};

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

interface ActiveRefreshTokenUse {
  generation: number;
  purpose: 'refresh' | 'revocation';
}

export class ChromeAuthStorage {
  readonly #local: StorageArea;
  readonly #session: StorageArea;
  #trustedAccess: Promise<void> | undefined;
  #authStateOperationQueue: Promise<void> = Promise.resolve();
  #activeRefreshTokenUse: ActiveRefreshTokenUse | undefined;
  #credentialStatePoisoned = false;

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
    await this.#serializeAuthStateOperation(() =>
      this.#withTrustedAccess(() => this.#session.set({ [AUTH_ATTEMPT_KEY]: attempt })),
    );
  }

  async loadAttempt(): Promise<AuthorizationAttempt> {
    return this.#serializeAuthStateOperation(() =>
      this.#withTrustedAccess(async () => {
        const stored = await this.#session.get(AUTH_ATTEMPT_KEY);
        const attempt = stored[AUTH_ATTEMPT_KEY];
        if (isAuthorizationAttempt(attempt)) {
          return attempt;
        }
        if (attempt !== undefined) {
          await this.#session.remove(AUTH_ATTEMPT_KEY);
        }
        throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
      }),
    );
  }

  async clearAttempt(): Promise<void> {
    await this.#serializeAuthStateOperation(() =>
      this.#withTrustedAccess(() => this.#session.remove(AUTH_ATTEMPT_KEY)),
    );
  }

  async saveInitialCredentials(
    credentials: ExchangedProviderCredentials,
    now: number,
  ): Promise<void> {
    await this.#serializeAuthStateOperation(() =>
      this.#withTrustedAccess(async () => {
        this.#activeRefreshTokenUse = undefined;
        await this.#failClosedCredentialOperation(() =>
          this.#commitCredentials(1, credentials, now),
        );
        this.#credentialStatePoisoned = false;
      }),
    );
  }

  async restoreCredentials(): Promise<RestoredCredentialState> {
    return this.#serializeAuthStateOperation(() =>
      this.#withTrustedAccess(() => {
        this.#requireUsableCredentialState();
        if (this.#activeRefreshTokenUse !== undefined) {
          throw new ExtensionAuthError('AUTH_REFRESH_FAILED');
        }
        return this.#failClosedCredentialOperation(async () => {
          const [localState, sessionState] = await Promise.all([
            this.#local.get(REFRESH_CREDENTIAL_KEY),
            this.#session.get(ACCESS_CREDENTIAL_KEY),
          ]);
          const refreshRecord = localState[REFRESH_CREDENTIAL_KEY];
          const accessRecord = sessionState[ACCESS_CREDENTIAL_KEY];

          if (
            (refreshRecord === undefined || isLocallyClearedRefreshRecord(refreshRecord)) &&
            accessRecord === undefined
          ) {
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
    return this.#serializeAuthStateOperation(() =>
      this.#withTrustedAccess(async () => {
        this.#requireUsableCredentialState();
        if (this.#activeRefreshTokenUse !== undefined) {
          throw new ExtensionAuthError('AUTH_REFRESH_FAILED');
        }
        const grant = await this.#failClosedCredentialOperation(() =>
          this.#claimRefreshToken(now, false),
        );
        if (grant === null) {
          throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
        }
        this.#activeRefreshTokenUse = { generation: grant.generation, purpose: 'refresh' };
        return grant;
      }),
    );
  }

  async beginRevocation(now: number): Promise<RefreshGrant | null> {
    return this.#serializeAuthStateOperation(() =>
      this.#withTrustedAccess(async () => {
        this.#requireUsableCredentialState();
        if (this.#activeRefreshTokenUse !== undefined) {
          throw new ExtensionAuthError('AUTH_REFRESH_FAILED');
        }
        const grant = await this.#failClosedCredentialOperation(() =>
          this.#claimRefreshToken(now, true),
        );
        if (grant !== null) {
          this.#activeRefreshTokenUse = { generation: grant.generation, purpose: 'revocation' };
        }
        return grant;
      }),
    );
  }

  async saveRefreshedCredentials(
    generation: number,
    credentials: ExchangedProviderCredentials,
    now: number,
  ): Promise<void> {
    await this.#serializeAuthStateOperation(() =>
      this.#withTrustedAccess(async () => {
        this.#requireUsableCredentialState();
        if (
          this.#activeRefreshTokenUse?.purpose !== 'refresh' ||
          this.#activeRefreshTokenUse.generation !== generation
        ) {
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
          this.#activeRefreshTokenUse = undefined;
        }
      }),
    );
  }

  async clearCredentials(): Promise<void> {
    await this.#serializeAuthStateOperation(async () => {
      try {
        await this.#removeWithTrustedAccess([
          () => this.#local.remove(REFRESH_CREDENTIAL_KEY),
          () => this.#session.remove(ACCESS_CREDENTIAL_KEY),
        ]);
      } finally {
        this.#activeRefreshTokenUse = undefined;
      }
    });
  }

  async clearAuthenticationState(): Promise<void> {
    await this.#serializeAuthStateOperation(async () => {
      try {
        await this.#removeWithTrustedAccess([
          () => this.#local.remove(REFRESH_CREDENTIAL_KEY),
          () => this.#session.remove(ACCESS_CREDENTIAL_KEY),
          () => this.#session.remove(AUTH_ATTEMPT_KEY),
        ]);
      } finally {
        this.#activeRefreshTokenUse = undefined;
      }
    });
  }

  async #claimRefreshToken(now: number, allowSignedOut: boolean): Promise<RefreshGrant | null> {
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
      (readyRecord === undefined || isLocallyClearedRefreshRecord(readyRecord)) &&
      accessRecord === undefined &&
      allowSignedOut
    ) {
      return null;
    }
    if (!isCommittedReadyRecord(readyRecord) || readyRecord.generation >= Number.MAX_SAFE_INTEGER) {
      throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
    }
    if (
      accessRecord !== undefined &&
      (!isStoredAccessCredential(accessRecord) ||
        accessRecord.generation !== readyRecord.generation)
    ) {
      throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
    }

    const grant: RefreshGrant = {
      generation: readyRecord.generation + 1,
      refreshToken: readyRecord.refreshToken,
    };
    const inProgress: RefreshInProgressRecord = {
      version: 1,
      status: 'refresh_in_progress',
      generation: grant.generation,
      startedAt: now,
    };
    await this.#local.set({ [REFRESH_CREDENTIAL_KEY]: inProgress });
    await this.#session.remove(ACCESS_CREDENTIAL_KEY);
    return grant;
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

  #serializeAuthStateOperation<T>(operation: () => Promise<T>): Promise<T> {
    const result = this.#authStateOperationQueue.then(operation, operation);
    this.#authStateOperationQueue = result.then(
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
    const invalidationConfirmed = await this.#writeCredentialInvalidationBestEffort();
    const results = await Promise.allSettled(
      [
        () => this.#local.remove(REFRESH_CREDENTIAL_KEY),
        () => this.#session.remove(ACCESS_CREDENTIAL_KEY),
      ].map(invokeStorageOperation),
    );
    if (!invalidationConfirmed && results[0]?.status === 'rejected') {
      await this.#writeCredentialInvalidationBestEffort();
    }
    const cleared = results.every((result) => result.status === 'fulfilled');
    if (!cleared) {
      this.#credentialStatePoisoned = true;
    } else {
      this.#credentialStatePoisoned = false;
    }
    return cleared;
  }

  async #removeWithTrustedAccess(removals: readonly (() => Promise<void>)[]): Promise<void> {
    try {
      await this.#ensureTrustedAccess();
    } catch {
      // Cleanup remains safe after both access-level gates settle because no credential is read.
    }

    const invalidationConfirmed = await this.#writeCredentialInvalidationBestEffort();
    const results = await Promise.allSettled(removals.map(invokeStorageOperation));
    if (!invalidationConfirmed && results[0]?.status === 'rejected') {
      await this.#writeCredentialInvalidationBestEffort();
    }
    if (results.some((result) => result.status === 'rejected')) {
      this.#credentialStatePoisoned = true;
      throw new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE');
    }
    this.#credentialStatePoisoned = false;
  }

  async #writeCredentialInvalidationBestEffort(): Promise<boolean> {
    try {
      await this.#local.set({ [REFRESH_CREDENTIAL_KEY]: LOCALLY_CLEARED_REFRESH_RECORD });
      return true;
    } catch {
      return false;
    }
  }

  #requireUsableCredentialState(): void {
    if (this.#credentialStatePoisoned) {
      throw new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE');
    }
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
    this.#trustedAccess ??= Promise.allSettled(
      [
        () => this.#local.setAccessLevel(TRUSTED_CONTEXTS),
        () => this.#session.setAccessLevel(TRUSTED_CONTEXTS),
      ].map(invokeStorageOperation),
    ).then((results) => {
      if (results.some((result) => result.status === 'rejected')) {
        throw new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE');
      }
    });
    return this.#trustedAccess;
  }
}

function invokeStorageOperation(operation: () => Promise<void>): Promise<void> {
  return Promise.resolve().then(operation);
}
