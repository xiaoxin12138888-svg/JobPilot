import type { ExchangedProviderCredentials } from './provider-protocol';

const MAX_ACCESS_TOKEN_LIFETIME_MS = 600_000;
const MAX_CREDENTIAL_LENGTH = 16_384;

export interface ReadyRefreshRecord {
  version: 1;
  status: 'ready';
  generation: number;
  accessState: 'pending' | 'committed';
  refreshToken: string;
}

export interface RefreshInProgressRecord {
  version: 1;
  status: 'refresh_in_progress';
  generation: number;
  startedAt: number;
}

export interface LocallyClearedRefreshRecord {
  version: 1;
  status: 'locally_cleared';
}

export interface StoredAccessCredential {
  version: 1;
  generation: number;
  accessToken: string;
  accessTokenExpiresAt: number;
  storedAt: number;
}

export function isCommittedReadyRecord(value: unknown): value is ReadyRefreshRecord {
  return (
    isRecord(value) &&
    hasExactKeys(value, ['version', 'status', 'generation', 'accessState', 'refreshToken']) &&
    value.version === 1 &&
    value.status === 'ready' &&
    value.accessState === 'committed' &&
    isGeneration(value.generation) &&
    isBoundedCredential(value.refreshToken)
  );
}

export function isRefreshInProgressRecord(value: unknown): value is RefreshInProgressRecord {
  return (
    isRecord(value) &&
    hasExactKeys(value, ['version', 'status', 'generation', 'startedAt']) &&
    value.version === 1 &&
    value.status === 'refresh_in_progress' &&
    isGeneration(value.generation) &&
    isSafeTimestamp(value.startedAt)
  );
}

export function isLocallyClearedRefreshRecord(
  value: unknown,
): value is LocallyClearedRefreshRecord {
  return (
    isRecord(value) &&
    hasExactKeys(value, ['version', 'status']) &&
    value.version === 1 &&
    value.status === 'locally_cleared'
  );
}

export function isStoredAccessCredential(value: unknown): value is StoredAccessCredential {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      'version',
      'generation',
      'accessToken',
      'accessTokenExpiresAt',
      'storedAt',
    ]) &&
    value.version === 1 &&
    isGeneration(value.generation) &&
    isBoundedCredential(value.accessToken) &&
    isSafeTimestamp(value.storedAt) &&
    isSafeTimestamp(value.accessTokenExpiresAt) &&
    value.accessTokenExpiresAt > value.storedAt &&
    value.accessTokenExpiresAt - value.storedAt <= MAX_ACCESS_TOKEN_LIFETIME_MS
  );
}

export function areStorableCredentials(value: ExchangedProviderCredentials, now: number): boolean {
  return (
    isSafeTimestamp(now) &&
    isBoundedCredential(value.accessToken) &&
    isBoundedCredential(value.refreshToken) &&
    isSafeTimestamp(value.accessTokenExpiresAt) &&
    value.accessTokenExpiresAt > now &&
    value.accessTokenExpiresAt - now <= MAX_ACCESS_TOKEN_LIFETIME_MS
  );
}

export function isGeneration(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 1;
}

export function isSafeTimestamp(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
}

function isBoundedCredential(value: unknown): value is string {
  if (typeof value !== 'string' || value.length === 0 || value.length > MAX_CREDENTIAL_LENGTH) {
    return false;
  }
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code <= 0x20 || code > 0x7e) {
      return false;
    }
  }
  return true;
}

function hasExactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const storedKeys = Object.keys(value);
  return storedKeys.length === keys.length && keys.every((key) => Object.hasOwn(value, key));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
