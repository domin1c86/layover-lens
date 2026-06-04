import type { AuthSession, SessionDuration } from '../types'

const AUTH_SESSION_KEY = 'layover_lens_auth_session'
const SESSION_DURATION_KEY = 'layover_lens_session_duration'

export const DEFAULT_SESSION_DURATION: SessionDuration = 'day'
const VALID_DURATIONS = new Set<SessionDuration>(['day', 'week', 'month', 'half_year', 'year', 'forever'])

function isSessionDuration(value: unknown): value is SessionDuration {
  return typeof value === 'string' && VALID_DURATIONS.has(value as SessionDuration)
}

function isExpired(expiresAt: string | null): boolean {
  if (!expiresAt) return false
  const time = Date.parse(expiresAt)
  return Number.isNaN(time) || time <= Date.now()
}

export function getStoredSessionDuration(): SessionDuration {
  const stored = localStorage.getItem(SESSION_DURATION_KEY)
  return isSessionDuration(stored) ? stored : DEFAULT_SESSION_DURATION
}

export function setStoredSessionDuration(duration: SessionDuration): void {
  localStorage.setItem(SESSION_DURATION_KEY, duration)
}

export function saveAuthSession(session: AuthSession): void {
  localStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(session))
}

export function clearAuthSession(): void {
  localStorage.removeItem(AUTH_SESSION_KEY)
}

export function getStoredAuthSession(): AuthSession | null {
  const raw = localStorage.getItem(AUTH_SESSION_KEY)
  if (!raw) return null

  try {
    const session = JSON.parse(raw) as Partial<AuthSession>
    if (
      !session.user ||
      !isSessionDuration(session.sessionDuration) ||
      !('expiresAt' in session)
    ) {
      clearAuthSession()
      return null
    }
    if (isExpired(session.expiresAt ?? null)) {
      clearAuthSession()
      return null
    }
    const safeSession = {
      user: {
        ...session.user,
        email_verified: session.user.email_verified ?? true,
        totp_enabled: session.user.totp_enabled ?? false,
      },
      expiresAt: session.expiresAt ?? null,
      sessionDuration: session.sessionDuration,
    }
    saveAuthSession(safeSession)
    return safeSession
  } catch {
    clearAuthSession()
    return null
  }
}
