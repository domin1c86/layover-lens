import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { useLocale } from '../../context/LocaleContext'
import { useAuth } from '../../context/AuthContext'
import { Icon } from '../../icons'
import { getApiErrorMessage } from '../../services/api'
import type { SessionDuration } from '../../types'
import './AuthModals.css'

interface RegisterModalProps {
  isOpen: boolean
  onClose: () => void
  onSwitchToLogin: () => void
  prefillEmail?: string
}

const overlayVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
  exit: { opacity: 0 },
}

const dialogVariants = {
  hidden: { opacity: 0, scale: 0.95, y: 30 },
  visible: { opacity: 1, scale: 1, y: 0 },
  exit: { opacity: 0, scale: 0.95, y: 30 },
}

function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

function formatDuration(duration: SessionDuration, lang: 'zh' | 'en'): string {
  const zh: Record<SessionDuration, string> = {
    day: '一天内有效',
    week: '一周内有效',
    month: '一月内有效',
    half_year: '半年内有效',
    year: '一年内有效',
    forever: '长期有效',
  }
  const en: Record<SessionDuration, string> = {
    day: 'valid for one day',
    week: 'valid for one week',
    month: 'valid for one month',
    half_year: 'valid for six months',
    year: 'valid for one year',
    forever: 'valid until you sign out',
  }
  return lang === 'en' ? en[duration] : zh[duration]
}

function successText(duration: SessionDuration, lang: 'zh' | 'en'): string {
  if (lang === 'en') {
    return `Registration successful. Your session is ${formatDuration(duration, lang)}. You can change this in Settings -> Account Security -> Session duration.`
  }
  return `注册成功，当前登录状态将在${formatDuration(duration, lang)}。你可以前往“设置 -> 账户安全 -> 登录保持时长”修改。`
}

export default function RegisterModal({ isOpen, onClose, onSwitchToLogin, prefillEmail }: RegisterModalProps) {
  const { lang, t } = useLocale()
  const { register } = useAuth()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!isOpen) return
    setUsername('')
    setEmail(prefillEmail || '')
    setPassword('')
    setConfirmPassword('')
    setShowPassword(false)
    setShowConfirmPassword(false)
    setError('')
    setSuccessMessage('')
    setLoading(false)
  }, [isOpen, prefillEmail])

  useEffect(() => {
    if (!successMessage) return
    const timer = setTimeout(() => {
      onClose()
    }, 4500)
    return () => clearTimeout(timer)
  }, [successMessage, onClose])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    },
    [onClose]
  )

  useEffect(() => {
    if (!isOpen) return
    document.addEventListener('keydown', handleKeyDown)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [isOpen, handleKeyDown])

  const handleSubmit = async () => {
    setError('')

    const trimmedUsername = username.trim()
    if (!trimmedUsername) {
      setError(t('auth.usernameRequired'))
      return
    }

    const trimmedEmail = email.trim()
    if (!trimmedEmail || !isValidEmail(trimmedEmail)) {
      setError(t('auth.emailInvalid'))
      return
    }

    if (password.length < 6) {
      setError(t('auth.passwordTooShort'))
      return
    }

    if (password !== confirmPassword) {
      setError(t('auth.passwordMismatch'))
      return
    }

    setLoading(true)
    try {
      const result = await register(trimmedEmail, trimmedUsername, password)
      setSuccessMessage(successText(result.sessionDuration, lang))
    } catch (err) {
      setError(getApiErrorMessage(err, lang === 'en' ? 'Registration failed. Please try again.' : '注册失败，请稍后重试。'))
    } finally {
      setLoading(false)
    }
  }

  const switchToLogin = () => {
    onClose()
    setTimeout(() => onSwitchToLogin(), 200)
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          key="register-overlay"
          className="auth-modal__overlay"
          onClick={onClose}
          role="dialog"
          aria-modal="true"
          aria-label={t('auth.registerTitle')}
          variants={overlayVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          transition={{ duration: 0.2 }}
        >
          <motion.div
            key="register-dialog"
            className="auth-modal__dialog"
            onClick={(e) => e.stopPropagation()}
            variants={dialogVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            transition={{ duration: 0.25, ease: 'easeOut' }}
          >
            <div className="auth-modal__header">
              <h3 className="auth-modal__title">{t('auth.registerTitle')}</h3>
              <button className="auth-modal__close" onClick={onClose} type="button" aria-label="Close">
                <Icon name="actions.closeEmoji" />
              </button>
            </div>

            <div className="auth-modal__body">
              {successMessage ? (
                <p className="auth-modal__success">{successMessage}</p>
              ) : (
                <>
                  <div className="auth-modal__field">
                    <label className="auth-modal__label">{t('auth.username')}</label>
                    <input
                      className="settings-panel__input"
                      type="text"
                      value={username}
                      onChange={(e) => { setUsername(e.target.value); setError('') }}
                      placeholder={t('auth.usernamePlaceholder')}
                      autoComplete="username"
                    />
                  </div>

                  <div className="auth-modal__field">
                    <label className="auth-modal__label">{t('auth.email')}</label>
                    <input
                      className="settings-panel__input"
                      type="email"
                      value={email}
                      onChange={(e) => { setEmail(e.target.value); setError('') }}
                      placeholder={t('auth.emailPlaceholder')}
                      autoComplete="email"
                    />
                  </div>

                  <div className="auth-modal__field">
                    <label className="auth-modal__label">{t('auth.password')}</label>
                    <div className="auth-modal__input-wrap">
                      <input
                        className="settings-panel__input"
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={(e) => { setPassword(e.target.value); setError('') }}
                        placeholder={t('auth.passwordPlaceholder')}
                        autoComplete="new-password"
                      />
                      <button
                        className="auth-modal__toggle-pw"
                        type="button"
                        onClick={() => setShowPassword((p) => !p)}
                        aria-label={showPassword ? 'Hide password' : 'Show password'}
                      >
                        <Icon name={showPassword ? 'actions.eyeOff' : 'actions.eyeOn'} size={16} />
                      </button>
                    </div>
                  </div>

                  <div className="auth-modal__field">
                    <label className="auth-modal__label">{t('auth.confirmPassword')}</label>
                    <div className="auth-modal__input-wrap">
                      <input
                        className="settings-panel__input"
                        type={showConfirmPassword ? 'text' : 'password'}
                        value={confirmPassword}
                        onChange={(e) => { setConfirmPassword(e.target.value); setError('') }}
                        placeholder={t('auth.confirmPasswordPlaceholder')}
                        autoComplete="new-password"
                      />
                      <button
                        className="auth-modal__toggle-pw"
                        type="button"
                        onClick={() => setShowConfirmPassword((p) => !p)}
                        aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                      >
                        <Icon name={showConfirmPassword ? 'actions.eyeOff' : 'actions.eyeOn'} size={16} />
                      </button>
                    </div>
                  </div>

                  {error && <p className="auth-modal__error">{error}</p>}

                  <button
                    className="settings-panel__btn settings-panel__btn--primary"
                    onClick={handleSubmit}
                    type="button"
                    disabled={loading}
                    style={{ width: '100%', marginTop: '4px' }}
                  >
                    {loading ? '...' : t('auth.registerBtn')}
                  </button>

                  <div className="auth-modal__footer">
                    <p className="auth-modal__switch-text">
                      {t('auth.hasAccount')}{' '}
                      <button className="auth-modal__link" type="button" onClick={switchToLogin}>
                        {t('auth.loginLink')}
                      </button>
                    </p>
                  </div>
                </>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
