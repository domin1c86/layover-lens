import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { useLocale } from '../../context/LocaleContext'
import { useAuth } from '../../context/AuthContext'
import { Icon } from '../../icons'
import { getApiErrorMessage } from '../../services/api'
import type { SessionDuration } from '../../types'
import './AuthModals.css'

interface LoginModalProps {
  isOpen: boolean
  onClose: () => void
  onSwitchToRegister: () => void
  onOpenForgotPassword: () => void
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
    return `Login successful. Your session is ${formatDuration(duration, lang)}. You can change this in Settings -> Account Security -> Session duration.`
  }
  return `登录成功，当前登录状态将在${formatDuration(duration, lang)}。你可以前往“设置 -> 账户安全 -> 登录保持时长”修改。`
}

export default function LoginModal({ isOpen, onClose, onSwitchToRegister, onOpenForgotPassword }: LoginModalProps) {
  const { lang, t } = useLocale()
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!isOpen) return
    setEmail('')
    setPassword('')
    setShowPassword(false)
    setError('')
    setSuccessMessage('')
    setLoading(false)
  }, [isOpen])

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

    const trimmedEmail = email.trim()
    if (!trimmedEmail || !isValidEmail(trimmedEmail)) {
      setError(t('auth.emailInvalid'))
      return
    }
    if (password.length < 6) {
      setError(t('auth.passwordTooShort'))
      return
    }

    setLoading(true)
    try {
      const result = await login(trimmedEmail, password)
      setSuccessMessage(successText(result.sessionDuration, lang))
    } catch (err) {
      setError(getApiErrorMessage(err, lang === 'en' ? 'Login failed. Please try again.' : '登录失败，请稍后重试。'))
    } finally {
      setLoading(false)
    }
  }

  const switchToRegister = () => {
    onClose()
    setTimeout(() => onSwitchToRegister(), 200)
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          key="login-overlay"
          className="auth-modal__overlay"
          onClick={onClose}
          role="dialog"
          aria-modal="true"
          aria-label={t('auth.loginTitle')}
          variants={overlayVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          transition={{ duration: 0.2 }}
        >
          <motion.div
            key="login-dialog"
            className="auth-modal__dialog"
            onClick={(e) => e.stopPropagation()}
            variants={dialogVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            transition={{ duration: 0.25, ease: 'easeOut' }}
          >
            <div className="auth-modal__header">
              <h3 className="auth-modal__title">{t('auth.loginTitle')}</h3>
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
                        autoComplete="current-password"
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

                  {error && <p className="auth-modal__error">{error}</p>}

                  <button
                    className="settings-panel__btn settings-panel__btn--primary"
                    onClick={handleSubmit}
                    type="button"
                    disabled={loading}
                    style={{ width: '100%', marginTop: '4px' }}
                  >
                    {loading ? '...' : t('auth.loginBtn')}
                  </button>

                  <div className="auth-modal__footer">
                    <button className="auth-modal__link" type="button" onClick={() => { onClose(); setTimeout(() => onOpenForgotPassword(), 200); }}>
                      {t('auth.forgotPassword')}
                    </button>
                    <p className="auth-modal__switch-text">
                      {t('auth.noAccount')}{' '}
                      <button className="auth-modal__link" type="button" onClick={switchToRegister}>
                        {t('auth.registerLink')}
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
