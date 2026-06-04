import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { AuthSession, SessionDuration, UserProfile } from '../types'
import { authApi } from '../services/api'
import {
  DEFAULT_SESSION_DURATION,
  clearAuthSession,
  getStoredAuthSession,
  getStoredSessionDuration,
  saveAuthSession,
  setStoredSessionDuration,
} from '../services/authStorage'

export type User = UserProfile

interface AuthSuccess {
  user: UserProfile
  expiresAt: string | null
  sessionDuration: SessionDuration
}

export interface TotpRequired {
  requiresTotp: true
  challengeToken: string
  expiresInSeconds: number
}

interface AuthContextType {
  user: UserProfile | null
  isLoggedIn: boolean
  loading: boolean
  sessionDuration: SessionDuration
  login: (email: string, password: string) => Promise<AuthSuccess | TotpRequired>
  verifyTotpLogin: (challengeToken: string, code: string) => Promise<AuthSuccess>
  register: (email: string, username: string, password: string, emailVerificationToken: string) => Promise<AuthSuccess>
  logout: () => Promise<void>
  deleteAccount: () => Promise<void>
  refreshUser: () => Promise<void>
  setSessionDuration: (duration: SessionDuration) => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

function toAuthSession(response: {
  user: UserProfile
  expires_at: string | null
  session_duration: SessionDuration
}): AuthSession {
  return {
    user: response.user,
    expiresAt: response.expires_at,
    sessionDuration: response.session_duration,
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(() => getStoredAuthSession()?.user ?? null)
  const [loading, setLoading] = useState(false)
  const [sessionDuration, setSessionDurationState] = useState<SessionDuration>(() => {
    return getStoredSessionDuration() || DEFAULT_SESSION_DURATION
  })

  const persistAuth = useCallback((session: AuthSession): AuthSuccess => {
    saveAuthSession(session)
    setUser(session.user)
    return {
      user: session.user,
      expiresAt: session.expiresAt,
      sessionDuration: session.sessionDuration,
    }
  }, [])

  const refreshUser = useCallback(async () => {
    const stored = getStoredAuthSession()

    setLoading(true)
    try {
      const profile = await authApi.getProfile()
      const nextSession: AuthSession = {
        user: profile,
        expiresAt: stored?.expiresAt ?? null,
        sessionDuration: stored?.sessionDuration ?? getStoredSessionDuration(),
      }
      saveAuthSession(nextSession)
      setUser(profile)
    } catch {
      if (stored) {
        clearAuthSession()
        setUser(null)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshUser()
  }, [refreshUser])

  useEffect(() => {
    const handleUnauthorized = () => {
      clearAuthSession()
      setUser(null)
    }
    window.addEventListener('auth:unauthorized', handleUnauthorized)
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized)
  }, [])

  const login = useCallback(
    async (email: string, password: string): Promise<AuthSuccess | TotpRequired> => {
      setLoading(true)
      try {
        const response = await authApi.login({
          email,
          password,
          session_duration: sessionDuration,
        })
        if (response.requires_totp) {
          return {
            requiresTotp: true,
            challengeToken: response.challenge_token,
            expiresInSeconds: response.expires_in_seconds,
          }
        }
        return persistAuth(toAuthSession(response))
      } finally {
        setLoading(false)
      }
    },
    [persistAuth, sessionDuration]
  )

  const verifyTotpLogin = useCallback(async (challengeToken: string, code: string): Promise<AuthSuccess> => {
    setLoading(true)
    try {
      const response = await authApi.verifyTotpLogin(challengeToken, code)
      return persistAuth(toAuthSession(response))
    } finally {
      setLoading(false)
    }
  }, [persistAuth])

  const register = useCallback(
    async (email: string, username: string, password: string, emailVerificationToken: string): Promise<AuthSuccess> => {
      setLoading(true)
      try {
        const response = await authApi.register({
          email,
          username,
          password,
          email_verification_token: emailVerificationToken,
          session_duration: sessionDuration,
        })
        return persistAuth(toAuthSession(response))
      } finally {
        setLoading(false)
      }
    },
    [persistAuth, sessionDuration]
  )

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      // Local logout should still complete if the server has already invalidated the token.
    } finally {
      clearAuthSession()
      setUser(null)
    }
  }, [])

  const deleteAccount = useCallback(async () => {
    setLoading(true)
    try {
      await authApi.deleteAccount()
      clearAuthSession()
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  const setSessionDuration = useCallback(async (duration: SessionDuration) => {
    const stored = getStoredAuthSession()
    if (!stored && !user) {
      setStoredSessionDuration(duration)
      setSessionDurationState(duration)
      return
    }

    const response = await authApi.updateSessionDuration(duration)
    const nextSession: AuthSession = {
      user: stored?.user ?? user!,
      expiresAt: response.expires_at,
      sessionDuration: response.session_duration,
    }
    saveAuthSession(nextSession)
    setStoredSessionDuration(response.session_duration)
    setSessionDurationState(response.session_duration)
  }, [user])

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      isLoggedIn: user !== null,
      loading,
      sessionDuration,
      login,
      verifyTotpLogin,
      register,
      logout,
      deleteAccount,
      refreshUser,
      setSessionDuration,
    }),
    [user, loading, sessionDuration, login, verifyTotpLogin, register, logout, deleteAccount, refreshUser, setSessionDuration]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
