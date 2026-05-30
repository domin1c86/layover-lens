import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import type { RoutePlan } from '../types'

const STORAGE_KEY = 'layover-lens-favorites'

function loadFavorites(): RoutePlan[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    if (!Array.isArray(parsed)) return []
    return parsed
  } catch {
    return []
  }
}

function saveFavorites(routes: RoutePlan[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(routes))
  } catch {
    // Quota exceeded or private mode
  }
}

interface FavoritesContextType {
  favorites: RoutePlan[]
  toggleFavorite: (route: RoutePlan) => void
  isFavorite: (routeId: string) => boolean
}

const FavoritesContext = createContext<FavoritesContextType | null>(null)

export function FavoritesProvider({ children }: { children: ReactNode }) {
  const [favorites, setFavorites] = useState<RoutePlan[]>(loadFavorites)

  useEffect(() => {
    saveFavorites(favorites)
  }, [favorites])

  const toggleFavorite = useCallback((route: RoutePlan) => {
    setFavorites((prev) => {
      const exists = prev.some((r) => r.id === route.id)
      if (exists) return prev.filter((r) => r.id !== route.id)
      return [route, ...prev]
    })
  }, [])

  const isFavorite = useCallback(
    (routeId: string) => favorites.some((r) => r.id === routeId),
    [favorites]
  )

  return (
    <FavoritesContext.Provider value={{ favorites, toggleFavorite, isFavorite }}>
      {children}
    </FavoritesContext.Provider>
  )
}

export function useFavoritesContext() {
  const ctx = useContext(FavoritesContext)
  if (!ctx) {
    throw new Error('useFavoritesContext must be used within <FavoritesProvider>')
  }
  return ctx
}
