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

interface AuthContextType {
  user: UserProfile | null
  isLoggedIn: boolean
  loading: boolean
  sessionDuration: SessionDuration
  login: (email: string, password: string) => Promise<AuthSuccess>
  register: (email: string, username: string, password: string) => Promise<AuthSuccess>
  logout: () => Promise<void>
  deleteAccount: () => Promise<void>
  refreshUser: () => Promise<void>
  setSessionDuration: (duration: SessionDuration) => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

function toAuthSession(response: {
  access_token: string
  user: UserProfile
  expires_at: string | null
  session_duration: SessionDuration
}): AuthSession {
  return {
    token: response.access_token,
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
    if (!stored) {
      setUser(null)
      return
    }

    setLoading(true)
    try {
      const profile = await authApi.getProfile()
      const nextSession = { ...stored, user: profile }
      saveAuthSession(nextSession)
      setUser(profile)
    } catch {
      clearAuthSession()
      setUser(null)
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
    async (email: string, password: string): Promise<AuthSuccess> => {
      setLoading(true)
      try {
        const response = await authApi.login({
          email,
          password,
          session_duration: sessionDuration,
        })
        return persistAuth(toAuthSession(response))
      } finally {
        setLoading(false)
      }
    },
    [persistAuth, sessionDuration]
  )

  const register = useCallback(
    async (email: string, username: string, password: string): Promise<AuthSuccess> => {
      setLoading(true)
      try {
        const response = await authApi.register({
          email,
          username,
          password,
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

  const setSessionDuration = useCallback((duration: SessionDuration) => {
    setStoredSessionDuration(duration)
    setSessionDurationState(duration)
  }, [])

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      isLoggedIn: user !== null,
      loading,
      sessionDuration,
      login,
      register,
      logout,
      deleteAccount,
      refreshUser,
      setSessionDuration,
    }),
    [user, loading, sessionDuration, login, register, logout, deleteAccount, refreshUser, setSessionDuration]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
