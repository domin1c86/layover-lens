import { describe, expect, it } from 'vitest'
import { getPasswordStrength, isValidEmail } from './security'

describe('security helpers', () => {
  it('validates email shape', () => {
    expect(isValidEmail('tester@example.com')).toBe(true)
    expect(isValidEmail('tester@example')).toBe(false)
  })

  it('classifies password strength and rejects unchanged passwords', () => {
    expect(getPasswordStrength('', 'oldpass')).toBe('empty')
    expect(getPasswordStrength('oldpass', 'oldpass')).toBe('weak')
    expect(getPasswordStrength('abc', 'oldpass')).toBe('weak')
    expect(getPasswordStrength('abcdef', 'oldpass')).toBe('medium')
    expect(getPasswordStrength('Abcdef123!', 'oldpass')).toBe('strong')
  })
})
