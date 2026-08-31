import { ApiClientError, type ExtensionBearerApiClient, type UserView } from '@jobpilot/api-client';

import type { InteractiveAuthorization, ValidatedAuthorizationCallback } from './authorization';
import { ExtensionAuthError } from './errors';
import type { ExchangedProviderCredentials } from './provider-protocol';
import type { ChromeAuthStorage } from './trusted-storage';

type AuthStorage = Pick<
  ChromeAuthStorage,
  'ensureTrustedAccess' | 'saveInitialCredentials' | 'restoreCredentials' | 'clearCredentials'
>;

interface ExtensionAuthServiceOptions {
  apiClient: ExtensionBearerApiClient;
  authorization: Pick<InteractiveAuthorization, 'launch'>;
  clock?: () => number;
  exchangeCode(callback: ValidatedAuthorizationCallback): Promise<ExchangedProviderCredentials>;
  storage: AuthStorage;
}

export class ExtensionAuthService {
  readonly #apiClient: ExtensionBearerApiClient;
  readonly #authorization: Pick<InteractiveAuthorization, 'launch'>;
  readonly #clock: () => number;
  readonly #exchangeCode: ExtensionAuthServiceOptions['exchangeCode'];
  readonly #storage: AuthStorage;

  constructor(options: ExtensionAuthServiceOptions) {
    this.#apiClient = options.apiClient;
    this.#authorization = options.authorization;
    this.#clock = options.clock ?? Date.now;
    this.#exchangeCode = options.exchangeCode;
    this.#storage = options.storage;
  }

  async signIn(): Promise<UserView> {
    await this.#storage.ensureTrustedAccess();
    const callback = await this.#authorization.launch();
    const credentials = await this.#exchangeCode(callback);
    await this.#storage.saveInitialCredentials(credentials, this.#clock());

    return this.#withApi401Cleanup(async () => {
      await this.#apiClient.establishIdentity(credentials.accessToken);
      return this.#apiClient.getCurrentUser(credentials.accessToken);
    });
  }

  async restoreCurrentUser(): Promise<UserView | null> {
    const restored = await this.#storage.restoreCredentials();
    if (restored.status === 'signed_out') {
      return null;
    }
    const access = restored.access;
    if (access === null) {
      throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
    }

    return this.#withApi401Cleanup(() => this.#apiClient.getCurrentUser(access.accessToken));
  }

  async #withApi401Cleanup<T>(operation: () => Promise<T>): Promise<T> {
    try {
      return await operation();
    } catch (error) {
      if (!(error instanceof ApiClientError) || error.status !== 401) {
        throw error;
      }
      await this.#storage.clearCredentials();
      throw new ExtensionAuthError('AUTHENTICATION_REQUIRED');
    }
  }
}
