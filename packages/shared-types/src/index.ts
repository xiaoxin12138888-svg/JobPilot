export interface ApiHealthResponse {
  status: 'ok';
  service: 'jobpilot-api';
}

export interface UserView {
  id: string;
  email: string;
  displayName: string | null;
  locale: string | null;
  timeZone: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface UserResponse {
  data: UserView;
}

export interface CsrfTokenResponse {
  data: {
    csrfToken: string;
  };
}
