import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { dict } from '../locales'

export type Lang = 'zh' | 'en'

interface LocaleContextType {
  lang: Lang
  setLang: (lang: Lang) => void
  t: (key: string, vars?: Record<string, string>) => string
}

const LocaleContext = createContext<LocaleContextType | undefined>(undefined)

function getInitialLang(): Lang {
  const stored = localStorage.getItem('locale')
  if (stored === 'en' || stored === 'zh') return stored
  const nav = navigator.language || ''
  if (nav.startsWith('en')) return 'en'
  return 'zh'
}

function getValueByPath(obj: any, path: string): string | undefined {
  const parts = path.split('.')
  let current = obj
  for (const part of parts) {
    if (current == null || typeof current !== 'object') return undefined
    current = current[part]
  }
  if (typeof current === 'string') return current
  return undefined
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(getInitialLang)

  useEffect(() => {
    localStorage.setItem('locale', lang)
  }, [lang])

  const setLang = (next: Lang) => setLangState(next)

  const t = (key: string, vars?: Record<string, string>): string => {
    let text = getValueByPath(dict[lang], key) ?? getValueByPath(dict['zh'], key) ?? key
    if (vars) {
      Object.entries(vars).forEach(([k, v]) => {
        text = text.replace(new RegExp(`{{${k}}}`, 'g'), v)
      })
    }
    return text
  }

  return (
    <LocaleContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LocaleContext.Provider>
  )
}

export function useLocale() {
  const ctx = useContext(LocaleContext)
  if (!ctx) throw new Error('useLocale must be used within LocaleProvider')
  return ctx
}
