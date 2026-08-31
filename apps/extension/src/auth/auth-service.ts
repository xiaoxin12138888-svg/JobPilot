import { ApiClientError, type ExtensionBearerApiClient, type UserView } from '@jobpilot/api-client';

import type { InteractiveAuthorization, ValidatedAuthorizationCallback } from './authorization';
import { ExtensionAuthError } from './errors';
import type { ExchangedProviderCredentials } from './provider-protocol';
import type { AccessCredential, ChromeAuthStorage } from './trusted-storage';

const ACCESS_TOKEN_REFRESH_WINDOW_MS = 30_000;

type AuthStorage = Pick<
  ChromeAuthStorage,
  | 'beginRefresh'
  | 'beginRevocation'
  | 'clearAuthenticationState'
  | 'clearCredentials'
  | 'ensureTrustedAccess'
  | 'restoreCredentials'
  | 'saveInitialCredentials'
  | 'saveRefreshedCredentials'
>;

export type ExtensionSignOutResult =
  { status: 'confirmed' } | { status: 'not_applicable' } | { status: 'unconfirmed' };

interface ExtensionAuthServiceOptions {
  apiClient: ExtensionBearerApiClient;
  authorization: Pick<InteractiveAuthorization, 'launch'>;
  clock?: () => number;
  exchangeCode(callback: ValidatedAuthorizationCallback): Promise<ExchangedProviderCredentials>;
  refreshCredentials(refreshToken: string): Promise<ExchangedProviderCredentials>;
  revokeRefreshGrant(refreshToken: string): Promise<void>;
  storage: AuthStorage;
}

interface RefreshInFlight {
  epoch: number;
  promise: Promise<AccessCredential>;
}

interface SignInInFlight {
  controller: AbortController;
  promise: Promise<UserView>;
}

interface RestoreInFlight {
  epoch: number;
  promise: Promise<UserView | null>;
}

export class ExtensionAuthService {
  readonly #apiClient: ExtensionBearerApiClient;
  readonly #authorization: Pick<InteractiveAuthorization, 'launch'>;
  readonly #clock: () => number;
  readonly #exchangeCode: ExtensionAuthServiceOptions['exchangeCode'];
  readonly #refreshCredentials: ExtensionAuthServiceOptions['refreshCredentials'];
  readonly #revokeRefreshGrant: ExtensionAuthServiceOptions['revokeRefreshGrant'];
  readonly #storage: AuthStorage;
  #lifecycleEpoch = 0;
  #refreshInFlight: RefreshInFlight | undefined;
  #restoreInFlight: RestoreInFlight | undefined;
  #signInInFlight: SignInInFlight | undefined;
  #uncommittedSignInGrantEpoch: number | undefined;
  #signOutInFlight: Promise<ExtensionSignOutResult> | undefined;

  constructor(options: ExtensionAuthServiceOptions) {
    this.#apiClient = options.apiClient;
    this.#authorization = options.authorization;
    this.#clock = options.clock ?? Date.now;
    this.#exchangeCode = options.exchangeCode;
    this.#refreshCredentials = options.refreshCredentials;
    this.#revokeRefreshGrant = options.revokeRefreshGrant;
    this.#storage = options.storage;
  }

  signIn(): Promise<UserView> {
    if (this.#signOutInFlight !== undefined) {
      return Promise.reject(new ExtensionAuthError('AUTHENTICATION_REQUIRED'));
    }
    if (this.#signInInFlight !== undefined) {
      return this.#signInInFlight.promise;
    }
    const epoch = ++this.#lifecycleEpoch;
    const controller = new AbortController();
    this.#uncommittedSignInGrantEpoch = epoch;
    const promise = this.#performSignIn(epoch, controller.signal);
    const inFlight = { controller, promise };
    this.#signInInFlight = inFlight;
    void promise.then(
      () => {
        if (this.#signInInFlight === inFlight) {
          this.#signInInFlight = undefined;
        }
        if (this.#uncommittedSignInGrantEpoch === epoch) {
          this.#uncommittedSignInGrantEpoch = undefined;
        }
      },
      () => {
        if (this.#signInInFlight === inFlight) {
          this.#signInInFlight = undefined;
        }
        if (this.#uncommittedSignInGrantEpoch === epoch) {
          this.#uncommittedSignInGrantEpoch = undefined;
        }
      },
    );
    return promise;
  }

  async #performSignIn(epoch: number, signal: AbortSignal): Promise<UserView> {
    let credentials: ExchangedProviderCredentials;
    try {
      await this.#storage.ensureTrustedAccess();
      this.#requireCurrentLifecycle(epoch);
      const callback = await this.#authorization.launch({ signal });
      this.#requireCurrentLifecycle(epoch);
      credentials = await this.#exchangeCode(callback);
      this.#requireCurrentLifecycle(epoch);
      await this.#storage.saveInitialCredentials(credentials, this.#clock());
      if (this.#uncommittedSignInGrantEpoch === epoch) {
        this.#uncommittedSignInGrantEpoch = undefined;
      }
      this.#requireCurrentLifecycle(epoch);
    } catch (error) {
      if (epoch !== this.#lifecycleEpoch) {
        throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
      }
      throw error;
    }

    const user = await this.#withApi401Cleanup(async () => {
      await this.#apiClient.establishIdentity(credentials.accessToken);
      this.#requireCurrentLifecycle(epoch);
      return this.#apiClient.getCurrentUser(credentials.accessToken);
    }, epoch);
    this.#requireCurrentLifecycle(epoch);
    return user;
  }

  restoreCurrentUser(): Promise<UserView | null> {
    if (this.#signOutInFlight !== undefined) {
      return this.#signOutInFlight.then(() => null);
    }
    const signIn = this.#signInInFlight;
    if (signIn !== undefined && !signIn.controller.signal.aborted) {
      return signIn.promise;
    }
    const epoch = this.#lifecycleEpoch;
    const existing = this.#restoreInFlight;
    if (existing?.epoch === epoch) {
      return existing.promise;
    }
    const promise = this.#performRestoreCurrentUser(epoch);
    const inFlight = { epoch, promise };
    this.#restoreInFlight = inFlight;
    void promise.then(
      () => {
        if (this.#restoreInFlight === inFlight) {
          this.#restoreInFlight = undefined;
        }
      },
      () => {
        if (this.#restoreInFlight === inFlight) {
          this.#restoreInFlight = undefined;
        }
      },
    );
    return promise;
  }

  async #performRestoreCurrentUser(epoch: number): Promise<UserView | null> {
    let access: AccessCredential | null | undefined = await this.#joinCurrentRefresh(epoch);
    if (access === undefined) {
      try {
        const restored = await this.#storage.restoreCredentials();
        this.#requireCurrentLifecycle(epoch);
        if (restored.status === 'signed_out') {
          return null;
        }
        access = this.#requiresRefresh(restored.access)
          ? await this.#refreshAccess(epoch)
          : restored.access;
      } catch (error) {
        if (epoch !== this.#lifecycleEpoch) {
          throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
        }
        if (!(error instanceof ExtensionAuthError) || error.code !== 'AUTH_REFRESH_FAILED') {
          throw error;
        }
        const refresh = this.#joinCurrentRefresh(epoch);
        if (refresh === undefined) {
          throw error;
        }
        access = await refresh;
      }
    }
    if (access === null || access === undefined) {
      throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
    }

    const user = await this.#withApi401Cleanup(
      () => this.#apiClient.getCurrentUser(access.accessToken),
      epoch,
    );
    this.#requireCurrentLifecycle(epoch);
    return user;
  }

  #joinCurrentRefresh(epoch: number): Promise<AccessCredential> | undefined {
    const refresh = this.#refreshInFlight;
    return refresh?.epoch === epoch ? refresh.promise : undefined;
  }

  signOut(): Promise<ExtensionSignOutResult> {
    if (this.#signOutInFlight !== undefined) {
      return this.#signOutInFlight;
    }
    const remoteGrantWasInFlight =
      this.#refreshInFlight !== undefined || this.#uncommittedSignInGrantEpoch !== undefined;
    this.#invalidateCurrentLifecycle();
    const signOut = this.#performSignOut(remoteGrantWasInFlight);
    this.#signOutInFlight = signOut;
    void signOut.then(
      () => {
        if (this.#signOutInFlight === signOut) {
          this.#signOutInFlight = undefined;
        }
      },
      () => {
        if (this.#signOutInFlight === signOut) {
          this.#signOutInFlight = undefined;
        }
      },
    );
    return signOut;
  }

  #requiresRefresh(access: AccessCredential | null): boolean {
    if (access === null) {
      return true;
    }
    const now = this.#clock();
    return (
      !Number.isSafeInteger(now) ||
      now < 0 ||
      access.accessTokenExpiresAt - now <= ACCESS_TOKEN_REFRESH_WINDOW_MS
    );
  }

  #refreshAccess(epoch: number): Promise<AccessCredential> {
    this.#requireCurrentLifecycle(epoch);
    const existing = this.#refreshInFlight;
    if (existing !== undefined) {
      if (existing.epoch !== epoch) {
        throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
      }
      return existing.promise;
    }

    const promise = this.#performRefresh(epoch);
    const inFlight = { epoch, promise };
    this.#refreshInFlight = inFlight;
    void promise.then(
      () => {
        if (this.#refreshInFlight === inFlight) {
          this.#refreshInFlight = undefined;
        }
      },
      () => {
        if (this.#refreshInFlight === inFlight) {
          this.#refreshInFlight = undefined;
        }
      },
    );
    return promise;
  }

  async #performRefresh(epoch: number): Promise<AccessCredential> {
    try {
      const grant = await this.#storage.beginRefresh(this.#clock());
      this.#requireCurrentLifecycle(epoch);
      const credentials = await this.#refreshCredentials(grant.refreshToken);
      this.#requireCurrentLifecycle(epoch);
      await this.#storage.saveRefreshedCredentials(grant.generation, credentials, this.#clock());
      this.#requireCurrentLifecycle(epoch);
      return {
        accessToken: credentials.accessToken,
        accessTokenExpiresAt: credentials.accessTokenExpiresAt,
      };
    } catch {
      if (epoch !== this.#lifecycleEpoch) {
        throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
      }
      await this.#storage.clearCredentials();
      throw new ExtensionAuthError('AUTH_REFRESH_FAILED');
    }
  }

  async #performSignOut(remoteGrantWasInFlight: boolean): Promise<ExtensionSignOutResult> {
    let grant: Awaited<ReturnType<AuthStorage['beginRevocation']>>;
    try {
      grant = await this.#storage.beginRevocation(this.#clock());
    } catch {
      await this.#clearAllAuthenticationState();
      return { status: 'unconfirmed' };
    }
    if (grant === null) {
      await this.#clearAllAuthenticationState();
      return { status: remoteGrantWasInFlight ? 'unconfirmed' : 'not_applicable' };
    }

    const [revocation, cleanup] = await Promise.allSettled([
      Promise.resolve().then(() => this.#revokeRefreshGrant(grant.refreshToken)),
      Promise.resolve().then(() => this.#storage.clearAuthenticationState()),
    ]);
    if (cleanup.status === 'rejected') {
      throw new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE');
    }
    return {
      status:
        revocation.status === 'fulfilled' && !remoteGrantWasInFlight ? 'confirmed' : 'unconfirmed',
    };
  }

  async #clearAllAuthenticationState(): Promise<void> {
    try {
      await this.#storage.clearAuthenticationState();
    } catch {
      throw new ExtensionAuthError('AUTH_STORAGE_UNAVAILABLE');
    }
  }

  async #withApi401Cleanup<T>(operation: () => Promise<T>, epoch: number): Promise<T> {
    try {
      return await operation();
    } catch (error) {
      if (epoch !== this.#lifecycleEpoch) {
        throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
      }
      if (!(error instanceof ApiClientError) || error.status !== 401) {
        throw error;
      }
      this.#invalidateCurrentLifecycle();
      await this.#storage.clearCredentials();
      throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
    }
  }

  #requireCurrentLifecycle(epoch: number): void {
    if (epoch !== this.#lifecycleEpoch) {
      throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
    }
  }

  #invalidateCurrentLifecycle(): void {
    this.#lifecycleEpoch += 1;
    this.#signInInFlight?.controller.abort();
  }
}
