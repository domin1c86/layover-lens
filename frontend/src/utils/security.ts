export type PasswordStrength = 'empty' | 'weak' | 'medium' | 'strong'

export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

export function getPasswordStrength(password: string, currentPassword: string): PasswordStrength {
  if (!password) return 'empty'
  if (currentPassword && password === currentPassword) return 'weak'
  if (password.length < 6) return 'weak'

  const groups = [
    /[a-z]/.test(password),
    /[A-Z]/.test(password),
    /\d/.test(password),
    /[^A-Za-z0-9]/.test(password),
  ].filter(Boolean).length

  if (password.length >= 10 && groups >= 3) return 'strong'
  return 'medium'
}
