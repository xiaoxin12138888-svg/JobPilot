import { isPopupResponseFor, type PopupRequest, type PopupSafeUser } from './popup-messages';
import {
  renderPopup,
  type PopupActions,
  type PopupOperation,
  type PopupViewState,
} from './popup-view';

interface PopupDependencies {
  sendMessage(request: PopupRequest): Promise<unknown>;
}

function getPopupRoot(): HTMLElement {
  const root = document.getElementById('popup-content');
  if (root === null) {
    throw new Error('Extension popup root was not found');
  }
  return root;
}

export async function initializePopup(dependencies: PopupDependencies): Promise<void> {
  const root = getPopupRoot();
  let operationInFlight = false;
  let state: PopupViewState = { status: 'authenticating', operation: 'restore' };

  const actions: PopupActions = {
    openWebApp,
    restore,
    signIn,
    signOut,
  };

  function updateState(nextState: PopupViewState): void {
    state = nextState;
    renderPopup(root, state, actions);
  }

  async function restore(): Promise<void> {
    if (!beginOperation('restore')) {
      return;
    }
    let nextState: PopupViewState;
    try {
      const response = await sendMessage({ type: 'GET_AUTH_STATE' });
      if (!isPopupResponseFor('GET_AUTH_STATE', response) || !response.ok) {
        nextState = { status: 'error', retry: 'restore' };
      } else {
        nextState =
          response.state.status === 'signed-out'
            ? response.state
            : signedInState(response.state.user, false, false);
      }
    } catch {
      nextState = { status: 'error', retry: 'restore' };
    }
    finishOperation(nextState);
  }

  async function signIn(): Promise<void> {
    if (!beginOperation('sign-in')) {
      return;
    }
    let nextState: PopupViewState;
    try {
      const response = await sendMessage({ type: 'SIGN_IN' });
      if (!isPopupResponseFor('SIGN_IN', response)) {
        nextState = { status: 'error', retry: 'sign-in' };
      } else if (response.ok) {
        nextState = signedInState(response.state.user, false, false);
      } else {
        nextState =
          response.error === 'AUTH_CANCELLED'
            ? { status: 'signed-out' }
            : { status: 'error', retry: 'sign-in' };
      }
    } catch {
      nextState = { status: 'error', retry: 'sign-in' };
    }
    finishOperation(nextState);
  }

  async function signOut(): Promise<void> {
    if (!beginOperation('sign-out')) {
      return;
    }
    let nextState: PopupViewState;
    try {
      const response = await sendMessage({ type: 'SIGN_OUT' });
      if (!isPopupResponseFor('SIGN_OUT', response) || !response.ok) {
        nextState = { status: 'error', retry: 'sign-out' };
      } else {
        nextState =
          response.revokeStatus === 'unconfirmed'
            ? { status: 'revoke-unconfirmed' }
            : { status: 'signed-out' };
      }
    } catch {
      nextState = { status: 'error', retry: 'sign-out' };
    }
    finishOperation(nextState);
  }

  async function openWebApp(): Promise<void> {
    if (operationInFlight || state.status !== 'signed-in') {
      return;
    }
    const user = state.user;
    operationInFlight = true;
    updateState(signedInState(user, true, false));
    let openFailed: boolean;
    try {
      const response = await sendMessage({ type: 'OPEN_WEB_APP' });
      openFailed = !isPopupResponseFor('OPEN_WEB_APP', response) || !response.ok;
    } catch {
      openFailed = true;
    }
    operationInFlight = false;
    updateState(signedInState(user, false, openFailed));
  }

  function beginOperation(operation: PopupOperation): boolean {
    if (operationInFlight) {
      return false;
    }
    operationInFlight = true;
    updateState({ status: 'authenticating', operation });
    return true;
  }

  function finishOperation(nextState: PopupViewState): void {
    operationInFlight = false;
    updateState(nextState);
  }

  function sendMessage(request: PopupRequest): Promise<unknown> {
    try {
      return Promise.resolve(dependencies.sendMessage(request));
    } catch (error) {
      return Promise.reject(error);
    }
  }

  renderPopup(root, state, actions);
  await restore();
}

function signedInState(
  user: PopupSafeUser,
  isOpening: boolean,
  openFailed: boolean,
): PopupViewState {
  return { status: 'signed-in', user, isOpening, openFailed };
}
