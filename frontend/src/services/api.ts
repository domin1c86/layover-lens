import axios from 'axios';
import type {
  SearchRequest,
  SearchResponse,
  CityListResponse,
  City,
  AiSessionResponse,
  AiSessionListResponse,
  AiSessionSummary,
  AiStreamEvent,
  AiConfirmRequest,
  AuthLoginRequest,
  AuthLoginResponse,
  AuthRegisterRequest,
  AuthTokenResponse,
  DeviceInfo,
  DeviceListResponse,
  EmailVerificationPurpose,
  EmailVerificationSendResponse,
  EmailVerificationVerifyResponse,
  ForgotPasswordCheckEmailResponse,
  ForgotPasswordSendCodeResponse,
  ForgotPasswordVerifyCodeResponse,
  SessionDuration,
  SessionDurationUpdateResponse,
  TotpSetupResponse,
  UserProfile,
} from '../types';
import { clearAuthSession } from './authStorage';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';
const CSRF_COOKIE_NAME = import.meta.env.VITE_CSRF_COOKIE_NAME || 'layover_lens_csrf';
const CSRF_HEADER_NAME = import.meta.env.VITE_CSRF_HEADER_NAME || 'X-CSRF-Token';
const CSRF_METHODS = new Set(['post', 'put', 'patch', 'delete']);

const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 10000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 搜索 API
function getCookieValue(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie.split('; ').find((entry) => entry.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : null;
}

apiClient.interceptors.request.use((config) => {
  const method = (config.method || 'get').toLowerCase();
  if (CSRF_METHODS.has(method)) {
    const csrfToken = getCookieValue(CSRF_COOKIE_NAME);
    if (csrfToken) {
      config.headers[CSRF_HEADER_NAME] = csrfToken;
    }
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401 || error?.response?.status === 403) {
      clearAuthSession();
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new Event('auth:unauthorized'));
      }
    }
    return Promise.reject(error);
  }
);

export function getApiErrorMessage(error: unknown, fallback = '请求失败，请稍后重试。'): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

export const authApi = {
  register: async (request: AuthRegisterRequest): Promise<AuthTokenResponse> => {
    const response = await apiClient.post<AuthTokenResponse>('/auth/register', request);
    return response.data;
  },

  login: async (request: AuthLoginRequest): Promise<AuthLoginResponse> => {
    const response = await apiClient.post<AuthLoginResponse>('/auth/login', request);
    return response.data;
  },

  verifyTotpLogin: async (challengeToken: string, code: string): Promise<AuthTokenResponse> => {
    const response = await apiClient.post<AuthTokenResponse>('/auth/login/totp', {
      challenge_token: challengeToken,
      code,
    });
    return response.data;
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/auth/logout');
  },

  deleteAccount: async (): Promise<void> => {
    await apiClient.delete('/user/account');
  },

  getProfile: async (): Promise<UserProfile> => {
    const response = await apiClient.get<UserProfile>('/user/profile');
    return response.data;
  },

  updateProfile: async (nickname: string): Promise<UserProfile> => {
    const response = await apiClient.put<UserProfile>('/user/profile', { nickname });
    return response.data;
  },

  updateAvatarPreset: async (presetId: string): Promise<UserProfile> => {
    const response = await apiClient.put<UserProfile>('/user/avatar/preset', {
      preset_id: presetId,
    });
    return response.data;
  },

  checkForgotPasswordEmail: async (email: string): Promise<ForgotPasswordCheckEmailResponse> => {
    const response = await apiClient.post<ForgotPasswordCheckEmailResponse>(
      '/auth/forgot-password/check-email',
      { email }
    );
    return response.data;
  },

  sendForgotPasswordCode: async (email: string): Promise<ForgotPasswordSendCodeResponse> => {
    const response = await apiClient.post<ForgotPasswordSendCodeResponse>(
      '/auth/forgot-password/send-code',
      { email }
    );
    return response.data;
  },

  verifyForgotPasswordCode: async (email: string, code: string): Promise<ForgotPasswordVerifyCodeResponse> => {
    const response = await apiClient.post<ForgotPasswordVerifyCodeResponse>(
      '/auth/forgot-password/verify-code',
      { email, code }
    );
    return response.data;
  },

  resetForgotPassword: async (resetToken: string, newPassword: string): Promise<void> => {
    await apiClient.post('/auth/forgot-password/reset', {
      reset_token: resetToken,
      new_password: newPassword,
    });
  },

  sendEmailVerificationCode: async (
    email: string,
    purpose: EmailVerificationPurpose
  ): Promise<EmailVerificationSendResponse> => {
    const response = await apiClient.post<EmailVerificationSendResponse>(
      '/auth/email-verification/send',
      { email, purpose }
    );
    return response.data;
  },

  verifyEmailVerificationCode: async (
    email: string,
    code: string,
    purpose: EmailVerificationPurpose
  ): Promise<EmailVerificationVerifyResponse> => {
    const response = await apiClient.post<EmailVerificationVerifyResponse>(
      '/auth/email-verification/verify',
      { email, code, purpose }
    );
    return response.data;
  },

  verifyCurrentEmail: async (verificationToken: string): Promise<UserProfile> => {
    const response = await apiClient.post<UserProfile>('/user/email/verify', {
      verification_token: verificationToken,
    });
    return response.data;
  },

  updateEmail: async (
    currentEmail: string,
    newEmail: string,
    verificationToken: string
  ): Promise<UserProfile> => {
    const response = await apiClient.put<UserProfile>('/user/email', {
      current_email: currentEmail,
      new_email: newEmail,
      verification_token: verificationToken,
    });
    return response.data;
  },

  checkPassword: async (currentPassword: string): Promise<boolean> => {
    const response = await apiClient.post<{ valid: boolean }>('/user/password/check', {
      current_password: currentPassword,
    });
    return response.data.valid;
  },

  updatePassword: async (currentPassword: string, newPassword: string): Promise<void> => {
    await apiClient.put('/user/password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
  },

  setupTotp: async (currentPassword: string): Promise<TotpSetupResponse> => {
    const response = await apiClient.post<TotpSetupResponse>('/user/totp/setup', {
      current_password: currentPassword,
    });
    return response.data;
  },

  enableTotp: async (code: string): Promise<UserProfile> => {
    const response = await apiClient.post<UserProfile>('/user/totp/enable', { code });
    return response.data;
  },

  disableTotp: async (currentPassword: string, code: string): Promise<UserProfile> => {
    const response = await apiClient.post<UserProfile>('/user/totp/disable', {
      current_password: currentPassword,
      code,
    });
    return response.data;
  },

  updateTotpEmailCodeReplacement: async (enabled: boolean): Promise<UserProfile> => {
    const response = await apiClient.put<UserProfile>('/user/totp/email-code-replacement', { enabled });
    return response.data;
  },

  updateSessionDuration: async (sessionDuration: SessionDuration): Promise<SessionDurationUpdateResponse> => {
    const response = await apiClient.put<SessionDurationUpdateResponse>('/user/session-duration', {
      session_duration: sessionDuration,
    });
    return response.data;
  },

  listDevices: async (): Promise<DeviceInfo[]> => {
    const response = await apiClient.get<DeviceListResponse>('/user/devices');
    return response.data.devices;
  },

  revokeDevice: async (deviceId: string): Promise<void> => {
    await apiClient.delete(`/user/devices/${deviceId}`);
  },
};

export const searchApi = {
  search: async (request: SearchRequest): Promise<SearchResponse> => {
    const response = await apiClient.post<SearchResponse>('/search', request);
    return response.data;
  },
};

// 城市 API
export const cityApi = {
  getCities: async (keyword?: string): Promise<City[]> => {
    const response = await apiClient.get<CityListResponse>('/cities', {
      params: keyword ? { keyword } : undefined,
    });
    return response.data.cities;
  },
};

// AI 搜索 API
export const aiSearchApi = {
  createSession: async (message: string, language?: string): Promise<AiSessionResponse> => {
    const response = await apiClient.post<AiSessionResponse>('/search/ai/sessions', {
      message,
      language,
      request_id: crypto.randomUUID(),
    });
    return response.data;
  },

  sendMessage: async (sessionId: string, message: string, language?: string): Promise<AiSessionResponse> => {
    const response = await apiClient.post<AiSessionResponse>(
      `/search/ai/sessions/${sessionId}/messages`,
      { message, language, request_id: crypto.randomUUID() }
    );
    return response.data;
  },

  confirm: async (sessionId: string, confirmed: boolean): Promise<AiSessionResponse> => {
    const response = await apiClient.post<AiSessionResponse>(
      `/search/ai/sessions/${sessionId}/confirm`,
      { confirmed, request_id: crypto.randomUUID() } as AiConfirmRequest
    );
    return response.data;
  },

  summarize: async (message: string, language?: string): Promise<{ title: string }> => {
    const response = await apiClient.post<{ title: string }>('/search/ai/summarize', {
      message,
      language: language || 'zh',
    });
    return response.data;
  },

  listSessions: async (): Promise<AiSessionSummary[]> => {
    const response = await apiClient.get<AiSessionListResponse>('/search/ai/sessions');
    return response.data.sessions;
  },

  getSession: async (sessionId: string): Promise<AiSessionResponse> => {
    const response = await apiClient.get<AiSessionResponse>(`/search/ai/sessions/${sessionId}`);
    return response.data;
  },

  renameSession: async (sessionId: string, title: string): Promise<AiSessionSummary> => {
    const response = await apiClient.put<AiSessionSummary>(`/search/ai/sessions/${sessionId}`, { title });
    return response.data;
  },

  deleteSession: async (sessionId: string): Promise<void> => {
    await apiClient.delete(`/search/ai/sessions/${sessionId}`);
  },

  stream: async (
    path: string,
    body: Record<string, unknown>,
    onEvent: (event: AiStreamEvent) => void,
    signal?: AbortSignal
  ): Promise<void> => {
    const csrfToken = getCookieValue(CSRF_COOKIE_NAME);
    const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
      method: 'POST',
      credentials: 'include',
      signal,
      headers: {
        'Content-Type': 'application/json',
        ...(csrfToken ? { [CSRF_HEADER_NAME]: csrfToken } : {}),
      },
      body: JSON.stringify({ ...body, request_id: crypto.randomUUID() }),
    });
    if (!response.ok || !response.body) {
      if (response.status === 401 || response.status === 403) {
        clearAuthSession();
        window.dispatchEvent(new Event('auth:unauthorized'));
      }
      throw new Error(`AI stream failed with status ${response.status}`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split('\n\n');
      buffer = frames.pop() || '';
      for (const frame of frames) {
        let eventName = '';
        let data = '';
        for (const line of frame.split('\n')) {
          if (line.startsWith('event:')) eventName = line.slice(6).trim();
          if (line.startsWith('data:')) data += line.slice(5).trim();
        }
        if (eventName && data) {
          onEvent({ event: eventName, ...JSON.parse(data) } as AiStreamEvent);
        }
      }
    }
  },

  streamCreate: (
    message: string,
    language: string,
    onEvent: (event: AiStreamEvent) => void,
    signal?: AbortSignal
  ) => aiSearchApi.stream('/search/ai/sessions/stream', { message, language }, onEvent, signal),

  streamMessage: (
    sessionId: string,
    message: string,
    language: string,
    onEvent: (event: AiStreamEvent) => void,
    signal?: AbortSignal
  ) => aiSearchApi.stream(`/search/ai/sessions/${sessionId}/messages/stream`, { message, language }, onEvent, signal),

  streamConfirm: (
    sessionId: string,
    confirmed: boolean,
    language: string,
    onEvent: (event: AiStreamEvent) => void,
    signal?: AbortSignal
  ) => aiSearchApi.stream(`/search/ai/sessions/${sessionId}/confirm/stream`, { confirmed, language }, onEvent, signal),
};

export default apiClient;
