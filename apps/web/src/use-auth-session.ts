import { useCallback, useEffect, useRef, useState } from 'react';

import { isAuthenticationRequired, type ApiClient, type UserView } from '@jobpilot/api-client';

export type AuthSessionState =
  | { status: 'checking' }
  | { status: 'signed-out'; focusLogin: boolean }
  | { status: 'authentication-error' }
  | { status: 'unavailable' }
  | {
      status: 'signed-in';
      user: UserView;
      isLoggingOut: boolean;
      logoutFailed: boolean;
    };

interface AuthSessionBoundary {
  state: AuthSessionState;
  retry(): void;
  logout(): void;
}

export function useAuthSession(
  apiClient: ApiClient,
  hasAuthenticationError: boolean,
): AuthSessionBoundary {
  const [state, setState] = useState<AuthSessionState>(
    hasAuthenticationError ? { status: 'authentication-error' } : { status: 'checking' },
  );
  const operation = useRef(0);
  const csrfToken = useRef<string | null>(null);
  const logoutInFlight = useRef(false);

  const checkSession = useCallback(
    async (showChecking: boolean) => {
      const currentOperation = ++operation.current;
      csrfToken.current = null;
      if (showChecking) {
        setState({ status: 'checking' });
      }
      try {
        const user = await apiClient.getCurrentUser();
        if (operation.current !== currentOperation) {
          return;
        }
        const resolvedCsrfToken = await apiClient.getWebCsrfToken();
        if (operation.current === currentOperation) {
          csrfToken.current = resolvedCsrfToken;
          setState({
            status: 'signed-in',
            user,
            isLoggingOut: false,
            logoutFailed: false,
          });
        }
      } catch (error: unknown) {
        if (operation.current !== currentOperation) {
          return;
        }
        setState(
          isAuthenticationRequired(error)
            ? { status: 'signed-out', focusLogin: false }
            : { status: 'unavailable' },
        );
      }
    },
    [apiClient],
  );

  useEffect(() => {
    if (hasAuthenticationError) {
      ++operation.current;
      csrfToken.current = null;
      return;
    }

    void checkSession(false);
    return () => {
      ++operation.current;
    };
  }, [checkSession, hasAuthenticationError]);

  const logout = useCallback(async () => {
    if (state.status !== 'signed-in' || state.isLoggingOut || logoutInFlight.current) {
      return;
    }

    logoutInFlight.current = true;
    const currentOperation = ++operation.current;
    const currentUser = state.user;
    const currentCsrfToken = csrfToken.current;
    setState({
      status: 'signed-in',
      user: currentUser,
      isLoggingOut: true,
      logoutFailed: false,
    });

    try {
      if (currentCsrfToken === null) {
        throw new Error('Web CSRF token is unavailable');
      }
      await apiClient.logoutWebSession(currentCsrfToken);
      if (operation.current === currentOperation) {
        csrfToken.current = null;
        logoutInFlight.current = false;
        setState({ status: 'signed-out', focusLogin: true });
      }
    } catch {
      if (operation.current === currentOperation) {
        logoutInFlight.current = false;
        setState({
          status: 'signed-in',
          user: currentUser,
          isLoggingOut: false,
          logoutFailed: true,
        });
      }
    }
  }, [apiClient, state]);

  return {
    state,
    retry: () => {
      if (!hasAuthenticationError) {
        void checkSession(true);
      }
    },
    logout: () => void logout(),
  };
}
