import { useEffect, useRef } from 'react';

import type { ApiClient } from '@jobpilot/api-client';

import './styles.css';
import { type AuthSessionState, useAuthSession } from './use-auth-session';

interface AppProps {
  apiClient: ApiClient;
  hasAuthenticationError?: boolean;
}

export function App({ apiClient, hasAuthenticationError = false }: AppProps) {
  const { state, retry, logout } = useAuthSession(apiClient, hasAuthenticationError);
  const loginUrl = apiClient.getWebLoginUrl();
  const loginLink = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    if (state.status === 'signed-out' && state.focusLogin) {
      loginLink.current?.focus();
    }
  }, [state]);

  return (
    <main className="app-shell">
      <section className="auth-panel" aria-labelledby="jobpilot-title">
        <header className="brand-header">
          <p className="product-label">个人求职工作台</p>
          <h1 id="jobpilot-title">JobPilot</h1>
        </header>

        {state.status !== 'authentication-error' && state.status !== 'unavailable' && (
          <p className="visually-hidden" role="status" aria-live="polite">
            {authStatusAnnouncement(state.status)}
          </p>
        )}

        {state.status === 'checking' && (
          <div className="auth-state" aria-busy="true">
            <h2>正在检查登录状态…</h2>
            <p>请稍候。</p>
          </div>
        )}

        {state.status === 'signed-out' && (
          <div className="auth-state">
            <h2>登录后继续使用 JobPilot</h2>
            <p>登录由安全的托管页面完成，JobPilot Web 不保存身份提供方令牌。</p>
            <a ref={loginLink} className="primary-action" href={loginUrl}>
              登录
            </a>
          </div>
        )}

        {state.status === 'signed-in' && (
          <div className="auth-state">
            <div>
              <h2>欢迎，{state.user.displayName?.trim() || state.user.email}</h2>
              <p>你已通过 JobPilot 的服务器会话安全登录。</p>
            </div>
            <dl className="account-details">
              <div>
                <dt>邮箱</dt>
                <dd>{state.user.email}</dd>
              </div>
              <div>
                <dt>用户 ID</dt>
                <dd className="user-id">{state.user.id}</dd>
              </div>
            </dl>
            {state.logoutFailed && (
              <p className="inline-error" role="alert">
                暂时无法安全退出，会话可能仍然有效。请重试。
              </p>
            )}
            <button
              type="button"
              className="secondary-action"
              onClick={logout}
              disabled={state.isLoggingOut}
            >
              {state.isLoggingOut ? '正在退出…' : '退出'}
            </button>
          </div>
        )}

        {state.status === 'authentication-error' && (
          <div className="auth-state error-state" role="alert">
            <h2>登录未完成</h2>
            <p>请重新登录，或稍后再试。</p>
            <a className="primary-action" href={loginUrl}>
              重新登录
            </a>
          </div>
        )}

        {state.status === 'unavailable' && (
          <div className="auth-state error-state" role="alert">
            <h2>暂时无法确认登录状态</h2>
            <p>请检查网络连接后重试。</p>
            <button type="button" className="secondary-action" onClick={retry}>
              重试
            </button>
          </div>
        )}
      </section>
    </main>
  );
}

function authStatusAnnouncement(status: AuthSessionState['status']): string {
  switch (status) {
    case 'checking':
      return '正在检查登录状态';
    case 'signed-out':
      return '当前未登录';
    case 'signed-in':
      return '登录状态已确认';
    case 'authentication-error':
    case 'unavailable':
      return '';
  }
}
