import axios from 'axios';
import type {
  SearchRequest,
  SearchResponse,
  CityListResponse,
  City,
  AiSessionResponse,
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
  createSession: async (message: string): Promise<AiSessionResponse> => {
    const response = await apiClient.post<AiSessionResponse>('/search/ai/sessions', { message });
    return response.data;
  },

  sendMessage: async (sessionId: string, message: string, language?: string): Promise<AiSessionResponse> => {
    const response = await apiClient.post<AiSessionResponse>(
      `/search/ai/sessions/${sessionId}/messages`,
      { message, language }
    );
    return response.data;
  },

  confirm: async (sessionId: string, confirmed: boolean): Promise<AiSessionResponse> => {
    const response = await apiClient.post<AiSessionResponse>(
      `/search/ai/sessions/${sessionId}/confirm`,
      { confirmed } as AiConfirmRequest
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
};

export default apiClient;
