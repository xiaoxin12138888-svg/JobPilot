import type { UserView } from '@jobpilot/api-client';

import type { ExtensionAuthService, ExtensionSignOutResult } from './auth/auth-service';
import { ExtensionAuthError } from './auth/errors';
import {
  parsePopupRequest,
  type PopupRequest,
  type PopupResponse,
  type PopupSafeUser,
} from './popup-messages';

type BackgroundAuthService = Pick<
  ExtensionAuthService,
  'restoreCurrentUser' | 'signIn' | 'signOut'
>;

export interface PopupBackgroundDependencies {
  authService: BackgroundAuthService;
  openWebApp(): Promise<void>;
}

export interface PopupRuntimeBoundary {
  readonly id: string;
  getURL(path: string): string;
}

interface CreatePopupMessageListenerOptions {
  dependencies: PopupBackgroundDependencies;
  runtime: PopupRuntimeBoundary;
}

export type PopupMessageHandler = (request: PopupRequest) => Promise<PopupResponse>;

export function isTrustedPopupSender(
  sender: chrome.runtime.MessageSender,
  runtime: PopupRuntimeBoundary,
): boolean {
  let popupUrl: string;
  let extensionOrigin: string;
  try {
    popupUrl = runtime.getURL('popup.html');
    extensionOrigin = runtime.getURL('').replace(/\/$/u, '');
  } catch {
    return false;
  }

  return (
    sender.id === runtime.id &&
    sender.url === popupUrl &&
    sender.tab === undefined &&
    (sender.origin === undefined || sender.origin === extensionOrigin)
  );
}

export function createPopupMessageHandler(
  dependencies: PopupBackgroundDependencies,
): PopupMessageHandler {
  return async (request) => {
    try {
      switch (request.type) {
        case 'GET_AUTH_STATE': {
          const user = await dependencies.authService.restoreCurrentUser();
          return user === null ? signedOutResponse() : signedInResponse(user);
        }
        case 'SIGN_IN':
          return signedInResponse(await dependencies.authService.signIn());
        case 'SIGN_OUT':
          return signOutResponse(await dependencies.authService.signOut());
        case 'OPEN_WEB_APP':
          await dependencies.openWebApp();
          return { ok: true };
      }
    } catch (error) {
      return safeFailure(request.type, error);
    }
  };
}

export function createPopupMessageListener({
  dependencies,
  runtime,
}: CreatePopupMessageListenerOptions): (
  message: unknown,
  sender: chrome.runtime.MessageSender,
  sendResponse: (response: PopupResponse) => void,
) => boolean {
  const handleMessage = createPopupMessageHandler(dependencies);

  return (message, sender, sendResponse) => {
    if (!isTrustedPopupSender(sender, runtime)) {
      return false;
    }

    const request = parsePopupRequest(message);
    if (request === undefined) {
      sendResponse({ ok: false, error: 'INVALID_REQUEST' });
      return false;
    }

    void Promise.resolve()
      .then(() => handleMessage(request))
      .then(
        (response) => sendResponse(response),
        () => sendResponse(fallbackFailure(request.type)),
      );
    return true;
  };
}

function signedOutResponse(): PopupResponse {
  return { ok: true, state: { status: 'signed-out' } };
}

function signedInResponse(user: UserView): PopupResponse {
  return {
    ok: true,
    state: { status: 'signed-in', user: toPopupSafeUser(user) },
  };
}

function signOutResponse(result: ExtensionSignOutResult): PopupResponse {
  return {
    ok: true,
    state: { status: 'signed-out' },
    revokeStatus: result.status,
  };
}

function toPopupSafeUser(user: UserView): PopupSafeUser {
  return {
    id: user.id,
    email: user.email,
    displayName: user.displayName,
  };
}

function safeFailure(requestType: PopupRequest['type'], error: unknown): PopupResponse {
  if (requestType === 'OPEN_WEB_APP') {
    return { ok: false, error: 'OPEN_WEB_APP_FAILED' };
  }
  if (error instanceof ExtensionAuthError) {
    if (requestType === 'GET_AUTH_STATE' && isCredentialFreeFailure(error)) {
      return signedOutResponse();
    }
    if (requestType === 'SIGN_IN' && error.code === 'AUTH_CANCELLED') {
      return { ok: false, error: 'AUTH_CANCELLED' };
    }
    if (error.code === 'AUTH_STORAGE_UNAVAILABLE') {
      return { ok: false, error: 'AUTH_STORAGE_UNAVAILABLE' };
    }
  }
  return { ok: false, error: 'AUTH_UNAVAILABLE' };
}

function isCredentialFreeFailure(error: ExtensionAuthError): boolean {
  return error.code === 'AUTHENTICATION_REQUIRED' || error.code === 'AUTH_REFRESH_FAILED';
}

function fallbackFailure(requestType: PopupRequest['type']): PopupResponse {
  return requestType === 'OPEN_WEB_APP'
    ? { ok: false, error: 'OPEN_WEB_APP_FAILED' }
    : { ok: false, error: 'AUTH_UNAVAILABLE' };
}
