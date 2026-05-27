import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { LocaleProvider, useLocale } from './LocaleContext'

describe('LocaleContext', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('defaults to zh when navigator.language is zh-CN', () => {
    Object.defineProperty(window, 'navigator', {
      value: { language: 'zh-CN' },
      writable: true,
    })
    const { result } = renderHook(() => useLocale(), { wrapper: LocaleProvider })
    expect(result.current.lang).toBe('zh')
  })

  it('defaults to en when navigator.language is en-US', () => {
    Object.defineProperty(window, 'navigator', {
      value: { language: 'en-US' },
      writable: true,
    })
    const { result } = renderHook(() => useLocale(), { wrapper: LocaleProvider })
    expect(result.current.lang).toBe('en')
  })

  it('reads locale from localStorage', () => {
    localStorage.setItem('locale', 'en')
    const { result } = renderHook(() => useLocale(), { wrapper: LocaleProvider })
    expect(result.current.lang).toBe('en')
  })

  it('setLang persists to localStorage', () => {
    const { result } = renderHook(() => useLocale(), { wrapper: LocaleProvider })
    act(() => {
      result.current.setLang('en')
    })
    expect(result.current.lang).toBe('en')
    expect(localStorage.getItem('locale')).toBe('en')
  })

  it('t() returns Chinese translation by default', () => {
    Object.defineProperty(window, 'navigator', {
      value: { language: 'zh-CN' },
      writable: true,
    })
    const { result } = renderHook(() => useLocale(), { wrapper: LocaleProvider })
    expect(result.current.t('searchBar.from')).toBe('出发地')
  })

  it('t() returns English after switching', () => {
    const { result } = renderHook(() => useLocale(), { wrapper: LocaleProvider })
    act(() => {
      result.current.setLang('en')
    })
    expect(result.current.t('searchBar.from')).toBe('From')
  })

  it('t() falls back to key when translation missing', () => {
    const { result } = renderHook(() => useLocale(), { wrapper: LocaleProvider })
    expect(result.current.t('nonexistent.key')).toBe('nonexistent.key')
  })
})
