import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from './AuthContext'
import { getStoredAuthSession, saveAuthSession, setStoredSessionDuration } from '../services/authStorage'
import type { AuthTokenResponse, SessionDuration, UserProfile } from '../types'

const mocks = vi.hoisted(() => ({
  authApi: {
    register: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    deleteAccount: vi.fn(),
    getProfile: vi.fn(),
  },
}))

vi.mock('../services/api', () => ({
  authApi: mocks.authApi,
}))

const profile: UserProfile = {
  id: 'user_1',
  username: 'tester',
  email: 'tester@example.com',
  nickname: null,
  avatar_url: null,
  created_at: '2026-01-01T00:00:00',
}

function tokenResponse(duration: SessionDuration = 'day'): AuthTokenResponse {
  return {
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
    mocks.authApi.getProfile.mockResolvedValue(profile)
  })

  it('logs in with the default one-day duration and stores the token', async () => {
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
    expect(success!.sessionDuration).toBe('day')
    expect(result.current.user?.email).toBe('tester@example.com')
    expect(getStoredAuthSession()?.token).toBe('token_day')
  })

  it('registers with the configured session duration', async () => {
    setStoredSessionDuration('month')
    mocks.authApi.register.mockResolvedValue(tokenResponse('month'))
    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider })

    await act(async () => {
      await result.current.register('tester@example.com', 'tester', 'secret123')
    })

    expect(mocks.authApi.register).toHaveBeenCalledWith({
      email: 'tester@example.com',
      username: 'tester',
      password: 'secret123',
      session_duration: 'month',
    })
    expect(getStoredAuthSession()?.sessionDuration).toBe('month')
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

  it('ignores an expired stored token on startup', () => {
    saveAuthSession({
      token: 'expired_token',
      user: profile,
      expiresAt: '2000-01-01T00:00:00',
      sessionDuration: 'day',
    })

    const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider })

    expect(result.current.user).toBeNull()
    expect(getStoredAuthSession()).toBeNull()
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
