export type ExtensionAuthErrorCode =
  | 'AUTH_CANCELLED'
  | 'AUTH_STATE_MISMATCH'
  | 'AUTH_ATTEMPT_EXPIRED'
  | 'AUTH_PROVIDER_ERROR'
  | 'AUTH_TOKEN_EXCHANGE_FAILED'
  | 'AUTH_REFRESH_FAILED'
  | 'AUTHENTICATION_REQUIRED'
  | 'AUTH_STORAGE_UNAVAILABLE';

export class ExtensionAuthError extends Error {
  readonly code: ExtensionAuthErrorCode;

  constructor(code: ExtensionAuthErrorCode) {
    super(code);
    this.name = 'ExtensionAuthError';
    this.code = code;
  }
}
