import { describe, expect, it } from 'vitest';

import { isPopupResponseFor, parsePopupRequest, type PopupRequest } from './popup-messages';

const requests: PopupRequest[] = [
  { type: 'GET_AUTH_STATE' },
  { type: 'SIGN_IN' },
  { type: 'SIGN_OUT' },
  { type: 'OPEN_WEB_APP' },
];

describe('parsePopupRequest', () => {
  it.each(requests)('accepts the exact $type request', (request) => {
    expect(parsePopupRequest(request)).toEqual(request);
  });

  it.each([
    null,
    undefined,
    [],
    {},
    { type: 'UNKNOWN' },
    { type: 'SIGN_IN', accessToken: 'must-not-cross-the-message-boundary' },
    { type: 'SIGN_OUT', refreshToken: 'must-not-cross-the-message-boundary' },
    { type: 'OPEN_WEB_APP', url: 'https://attacker.example.invalid/' },
  ])('rejects a malformed or non-exact request: %j', (request) => {
    expect(parsePopupRequest(request)).toBeUndefined();
  });
});

describe('isPopupResponseFor', () => {
  it('accepts only exact popup-safe auth states', () => {
    expect(
      isPopupResponseFor('GET_AUTH_STATE', {
        ok: true,
        state: { status: 'signed-out' },
      }),
    ).toBe(true);
    expect(
      isPopupResponseFor('GET_AUTH_STATE', {
        ok: true,
        state: {
          status: 'signed-in',
          user: { id: 'user-1', email: 'user@example.com', displayName: null },
        },
      }),
    ).toBe(true);
    expect(
      isPopupResponseFor('SIGN_IN', {
        ok: true,
        state: {
          status: 'signed-in',
          user: { id: 'user-1', email: 'user@example.com', displayName: 'Lin' },
        },
      }),
    ).toBe(true);
  });

  it('accepts the three truthful sign-out outcomes', () => {
    for (const revokeStatus of ['confirmed', 'not_applicable', 'unconfirmed']) {
      expect(
        isPopupResponseFor('SIGN_OUT', {
          ok: true,
          state: { status: 'signed-out' },
          revokeStatus,
        }),
      ).toBe(true);
    }
  });

  it('accepts the exact open-Web success and bounded error shapes', () => {
    expect(isPopupResponseFor('OPEN_WEB_APP', { ok: true })).toBe(true);
    expect(isPopupResponseFor('OPEN_WEB_APP', { ok: false, error: 'OPEN_WEB_APP_FAILED' })).toBe(
      true,
    );
    expect(isPopupResponseFor('SIGN_IN', { ok: false, error: 'AUTH_CANCELLED' })).toBe(true);
    expect(
      isPopupResponseFor('GET_AUTH_STATE', {
        ok: false,
        error: 'AUTH_STORAGE_UNAVAILABLE',
      }),
    ).toBe(true);
  });

  it.each([
    ['GET_AUTH_STATE', undefined],
    ['GET_AUTH_STATE', { ok: true, state: { status: 'signed-out' }, accessToken: 'secret' }],
    [
      'GET_AUTH_STATE',
      {
        ok: true,
        state: {
          status: 'signed-in',
          user: {
            id: 'user-1',
            email: 'user@example.com',
            displayName: null,
            identitySubject: 'provider-subject',
          },
        },
      },
    ],
    ['SIGN_IN', { ok: true, state: { status: 'signed-out' } }],
    ['SIGN_OUT', { ok: true, state: { status: 'signed-out' }, revokeStatus: 'queued_for_retry' }],
    ['SIGN_OUT', { ok: false, error: 'OPEN_WEB_APP_FAILED' }],
    ['OPEN_WEB_APP', { ok: true, url: 'https://jobpilot.example.invalid/' }],
    ['OPEN_WEB_APP', { ok: false, error: 'AUTH_UNAVAILABLE' }],
  ] as const)('rejects an invalid %s response', (requestType, response) => {
    expect(isPopupResponseFor(requestType, response)).toBe(false);
  });
});
