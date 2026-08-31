export type PopupRequest =
  | { type: 'GET_AUTH_STATE' }
  | { type: 'SIGN_IN' }
  | { type: 'SIGN_OUT' }
  | { type: 'OPEN_WEB_APP' };

export type PopupRequestType = PopupRequest['type'];

export interface PopupSafeUser {
  id: string;
  email: string;
  displayName: string | null;
}

export type PopupAuthState =
  { status: 'signed-out' } | { status: 'signed-in'; user: PopupSafeUser };

export type PopupRevokeStatus = 'confirmed' | 'not_applicable' | 'unconfirmed';

export type PopupErrorCode =
  | 'INVALID_REQUEST'
  | 'AUTH_CANCELLED'
  | 'AUTH_UNAVAILABLE'
  | 'AUTH_STORAGE_UNAVAILABLE'
  | 'OPEN_WEB_APP_FAILED';

type PopupFailure = { ok: false; error: PopupErrorCode };

export type GetAuthStateResponse = { ok: true; state: PopupAuthState } | PopupFailure;

export type SignInResponse =
  { ok: true; state: Extract<PopupAuthState, { status: 'signed-in' }> } | PopupFailure;

export type SignOutResponse =
  | {
      ok: true;
      state: Extract<PopupAuthState, { status: 'signed-out' }>;
      revokeStatus: PopupRevokeStatus;
    }
  | PopupFailure;

export type OpenWebAppResponse = { ok: true } | PopupFailure;

export interface PopupResponseMap {
  GET_AUTH_STATE: GetAuthStateResponse;
  SIGN_IN: SignInResponse;
  SIGN_OUT: SignOutResponse;
  OPEN_WEB_APP: OpenWebAppResponse;
}

export type PopupResponse = PopupResponseMap[PopupRequestType];

const REQUEST_TYPES: ReadonlySet<PopupRequestType> = new Set([
  'GET_AUTH_STATE',
  'SIGN_IN',
  'SIGN_OUT',
  'OPEN_WEB_APP',
]);

const AUTH_ERRORS: ReadonlySet<PopupErrorCode> = new Set([
  'INVALID_REQUEST',
  'AUTH_UNAVAILABLE',
  'AUTH_STORAGE_UNAVAILABLE',
]);

export function parsePopupRequest(value: unknown): PopupRequest | undefined {
  if (
    !isRecord(value) ||
    !hasExactKeys(value, ['type']) ||
    typeof value.type !== 'string' ||
    !REQUEST_TYPES.has(value.type as PopupRequestType)
  ) {
    return undefined;
  }
  return { type: value.type as PopupRequestType };
}

export function isPopupResponseFor(
  requestType: PopupRequestType,
  value: unknown,
): value is PopupResponseMap[typeof requestType] {
  if (!isRecord(value) || typeof value.ok !== 'boolean') {
    return false;
  }
  if (!value.ok) {
    return isAllowedFailure(requestType, value);
  }

  switch (requestType) {
    case 'GET_AUTH_STATE':
      return hasExactKeys(value, ['ok', 'state']) && isPopupAuthState(value.state);
    case 'SIGN_IN':
      return hasExactKeys(value, ['ok', 'state']) && isSignedInState(value.state);
    case 'SIGN_OUT':
      return (
        hasExactKeys(value, ['ok', 'state', 'revokeStatus']) &&
        isSignedOutState(value.state) &&
        isRevokeStatus(value.revokeStatus)
      );
    case 'OPEN_WEB_APP':
      return hasExactKeys(value, ['ok']);
  }
}

function isAllowedFailure(requestType: PopupRequestType, value: Record<string, unknown>): boolean {
  if (
    !hasExactKeys(value, ['ok', 'error']) ||
    typeof value.error !== 'string' ||
    value.ok !== false
  ) {
    return false;
  }

  if (requestType === 'OPEN_WEB_APP') {
    return value.error === 'INVALID_REQUEST' || value.error === 'OPEN_WEB_APP_FAILED';
  }
  if (requestType === 'SIGN_IN' && value.error === 'AUTH_CANCELLED') {
    return true;
  }
  return AUTH_ERRORS.has(value.error as PopupErrorCode);
}

function isPopupAuthState(value: unknown): value is PopupAuthState {
  return isSignedOutState(value) || isSignedInState(value);
}

function isSignedOutState(
  value: unknown,
): value is Extract<PopupAuthState, { status: 'signed-out' }> {
  return isRecord(value) && hasExactKeys(value, ['status']) && value.status === 'signed-out';
}

function isSignedInState(
  value: unknown,
): value is Extract<PopupAuthState, { status: 'signed-in' }> {
  return (
    isRecord(value) &&
    hasExactKeys(value, ['status', 'user']) &&
    value.status === 'signed-in' &&
    isPopupSafeUser(value.user)
  );
}

function isPopupSafeUser(value: unknown): value is PopupSafeUser {
  return (
    isRecord(value) &&
    hasExactKeys(value, ['id', 'email', 'displayName']) &&
    isBoundedNonEmptyString(value.id, 200) &&
    isBoundedNonEmptyString(value.email, 254) &&
    (value.displayName === null || isBoundedString(value.displayName, 100))
  );
}

function isRevokeStatus(value: unknown): value is PopupRevokeStatus {
  return value === 'confirmed' || value === 'not_applicable' || value === 'unconfirmed';
}

function isBoundedNonEmptyString(value: unknown, maximumLength: number): value is string {
  return typeof value === 'string' && value.length > 0 && value.length <= maximumLength;
}

function isBoundedString(value: unknown, maximumLength: number): value is string {
  return typeof value === 'string' && value.length <= maximumLength;
}

function hasExactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actualKeys = Object.keys(value);
  return actualKeys.length === keys.length && keys.every((key) => Object.hasOwn(value, key));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
