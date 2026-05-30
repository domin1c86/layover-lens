import { describe, it, expect } from 'vitest'
import { dict } from './index'

describe('dictionary', () => {
  it('has zh and en keys', () => {
    expect(dict.zh).toBeDefined()
    expect(dict.en).toBeDefined()
  })

  it('zh has all required top-level namespaces', () => {
    const required = [
      'topNav',
      'searchBar',
      'searchTab',
      'aiChat',
      'calendar',
      'errors',
      'cityGroups',
      'optimize',
      'resultList',
      'footer',
    ]
    for (const ns of required) {
      expect(dict.zh[ns as keyof typeof dict.zh]).toBeDefined()
    }
  })

  it('en mirrors zh structure for all keys', () => {
    function checkMirror(zhObj: any, enObj: any, path: string) {
      if (typeof zhObj === 'string') {
        expect(typeof enObj).toBe('string')
        return
      }
      if (Array.isArray(zhObj)) {
        expect(Array.isArray(enObj)).toBe(true)
        expect(enObj.length).toBe(zhObj.length)
        return
      }
      for (const key of Object.keys(zhObj)) {
        expect(enObj).toHaveProperty(key)
        checkMirror(zhObj[key], enObj[key], `${path}.${key}`)
      }
    }
    checkMirror(dict.zh, dict.en, 'dict')
  })
})
