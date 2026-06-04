import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from './AuthContext'
import { getStoredAuthSession, saveAuthSession, setStoredSessionDuration } from '../services/authStorage'
import type { AuthTokenResponse, SessionDuration, UserProfile } from '../types'

const mocks = vi.hoisted(() => ({
  authApi: {
    register: vi.fn(),
    login: vi.fn(),
    verifyTotpLogin: vi.fn(),
    logout: vi.fn(),
    deleteAccount: vi.fn(),
    getProfile: vi.fn(),
    updateSessionDuration: vi.fn(),
  },
}))

vi.mock('../services/api', () => ({
  authApi: mocks.authApi,
}))

const profile: UserProfile = {
  id: 'user_1',
  username: 'tester',
  email: 'tester@example.com',
  email_verified: true,
  totp_enabled: false,
  nickname: null,
  avatar_url: null,
  created_at: '2026-01-01T00:00:00',
}

function tokenResponse(duration: SessionDuration = 'day'): AuthTokenResponse {
  return {
    requires_totp: false,
    user: profile,
    access_token: `token_${duration}`,
    token_type: 'bearer',
    expires_at: duration === 'forever' ? null : '2099-01-01T00:00:00',
    session_duration: duration,
  }
}

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    mocks.authApi.logout.mockResolvedValue(undefined)
    mocks.authApi.deleteAccount.mockResolvedValue(undefined)
    mocks.authApi.getProfile.mockRejectedValue(new Error('No cookie session'))
    mocks.authApi.updateSessionDuration.mockResolvedValue({
      expires_at: '2099-02-01T00:00:00',
      session_duration: 'week',
    })
  })

  it('logs in with the default one-day duration without storing the token', async () => {
    mocks.authApi.login.mockResolvedValue(tokenResponse('day'))
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider })

    let success: Awaited<ReturnType<typeof result.current.login>> | undefined
    await act(async () => {
      success = await result.current.login('tester@example.com', 'secret123')
    })

    expect(mocks.authApi.login).toHaveBeenCalledWith({
      email: 'tester@example.com',
      password: 'secret123',
      session_duration: 'day',
    })
    expect('sessionDuration' in success!).toBe(true)
    if ('sessionDuration' in success!) {
      expect(success.sessionDuration).toBe('day')
    }
    expect(result.current.user?.email).toBe('tester@example.com')
    expect(getStoredAuthSession()).toMatchObject({
      user: profile,
      sessionDuration: 'day',
    })
    expect(JSON.parse(localStorage.getItem('layover_lens_auth_session') || '{}').token).toBeUndefined()
  })

  it('registers with the configured session duration', async () => {
    setStoredSessionDuration('month')
    mocks.authApi.register.mockResolvedValue(tokenResponse('month'))
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider })

    await act(async () => {
      await result.current.register('tester@example.com', 'tester', 'secret123', 'verify_token')
    })

    expect(mocks.authApi.register).toHaveBeenCalledWith({
      email: 'tester@example.com',
      username: 'tester',
      password: 'secret123',
      email_verification_token: 'verify_token',
      session_duration: 'month',
    })
    expect(getStoredAuthSession()?.sessionDuration).toBe('month')
  })

  it('completes a TOTP login challenge before storing auth state', async () => {
    mocks.authApi.login.mockResolvedValue({
      requires_totp: true,
      challenge_token: 'challenge_token',
      expires_in_seconds: 300,
    })
    mocks.authApi.verifyTotpLogin.mockResolvedValue(tokenResponse('day'))
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider })

    let challenge: Awaited<ReturnType<typeof result.current.login>> | undefined
    await act(async () => {
      challenge = await result.current.login('tester@example.com', 'secret123')
    })
    expect('requiresTotp' in challenge!).toBe(true)
    expect(result.current.user).toBeNull()

    await act(async () => {
      await result.current.verifyTotpLogin('challenge_token', '123456')
    })

    expect(mocks.authApi.verifyTotpLogin).toHaveBeenCalledWith('challenge_token', '123456')
    expect(result.current.user?.email).toBe('tester@example.com')
  })

  it('clears local state on logout', async () => {
    mocks.authApi.login.mockResolvedValue(tokenResponse('week'))
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider })

    await act(async () => {
      await result.current.login('tester@example.com', 'secret123')
      await result.current.logout()
    })

    expect(mocks.authApi.logout).toHaveBeenCalledOnce()
    expect(result.current.user).toBeNull()
    expect(getStoredAuthSession()).toBeNull()
  })

  it('updates the current stored session duration through the backend', async () => {
    mocks.authApi.login.mockResolvedValue(tokenResponse('day'))
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider })

    await act(async () => {
      await result.current.login('tester@example.com', 'secret123')
      await result.current.setSessionDuration('week')
    })

    expect(mocks.authApi.updateSessionDuration).toHaveBeenCalledWith('week')
    expect(result.current.sessionDuration).toBe('week')
    expect(getStoredAuthSession()).toMatchObject({
      expiresAt: '2099-02-01T00:00:00',
      sessionDuration: 'week',
    })
  })

  it('deletes the account and clears local auth state', async () => {
    mocks.authApi.login.mockResolvedValue(tokenResponse('day'))
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider })

    await act(async () => {
      await result.current.login('tester@example.com', 'secret123')
      await result.current.deleteAccount()
    })

    expect(mocks.authApi.deleteAccount).toHaveBeenCalledOnce()
    expect(result.current.user).toBeNull()
    expect(getStoredAuthSession()).toBeNull()
  })

  it('ignores an expired stored session on startup', () => {
    saveAuthSession({
      user: profile,
      expiresAt: '2000-01-01T00:00:00',
      sessionDuration: 'day',
    })

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider })

    expect(result.current.user).toBeNull()
    expect(getStoredAuthSession()).toBeNull()
  })

  it('restores auth state from the backend profile when the cookie is valid', async () => {
    mocks.authApi.getProfile.mockResolvedValue(profile)

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider })

    await waitFor(() => expect(result.current.user?.email).toBe('tester@example.com'))
    expect(getStoredAuthSession()).toMatchObject({
      user: profile,
      sessionDuration: 'day',
    })
    expect(JSON.parse(localStorage.getItem('layover_lens_auth_session') || '{}').token).toBeUndefined()
  })

  it('clears auth state when a 401 event is emitted', async () => {
    mocks.authApi.login.mockResolvedValue(tokenResponse('day'))
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider })

    await act(async () => {
      await result.current.login('tester@example.com', 'secret123')
    })
    expect(result.current.isLoggedIn).toBe(true)

    act(() => {
      window.dispatchEvent(new Event('auth:unauthorized'))
    })

    await waitFor(() => expect(result.current.isLoggedIn).toBe(false))
    expect(getStoredAuthSession()).toBeNull()
  })
})
