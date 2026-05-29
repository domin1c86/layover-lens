import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

export interface User {
  email: string
  username: string
}

interface AuthContextType {
  user: User | null
  isLoggedIn: boolean
  login: (email: string) => void
  register: (email: string, username: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)

  const login = useCallback((email: string) => {
    const username = email.split('@')[0]
    setUser({ email, username })
  }, [])

  const register = useCallback((email: string, username: string) => {
    setUser({ email, username })
  }, [])

  const logout = useCallback(() => {
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, isLoggedIn: user !== null, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
