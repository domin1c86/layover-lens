import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { useLocale } from '../../context/LocaleContext'
import { useAuth } from '../../context/AuthContext'
import { Icon } from '../../icons'
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

export default function LoginModal({ isOpen, onClose, onSwitchToRegister, onOpenForgotPassword }: LoginModalProps) {
  const { t } = useLocale()
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!isOpen) return
    setEmail('')
    setPassword('')
    setShowPassword(false)
    setError('')
    setSuccess(false)
    setLoading(false)
  }, [isOpen])

  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => {
        onClose()
      }, 1500)
      return () => clearTimeout(timer)
    }
  }, [success, onClose])

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

  const handleSubmit = () => {
    setError('')

    const trimmedEmail = email.trim()
    if (!trimmedEmail) {
      setError(t('auth.emailInvalid'))
      return
    }
    if (!isValidEmail(trimmedEmail)) {
      setError(t('auth.emailInvalid'))
      return
    }
    if (!password) {
      setError(t('auth.passwordTooShort'))
      return
    }
    if (password.length < 6) {
      setError(t('auth.passwordTooShort'))
      return
    }

    setLoading(true)
    // Mock login — replace with real API call when backend is ready
    console.log('[模拟] 登录:', { email: trimmedEmail, password })
    setTimeout(() => {
      login(trimmedEmail)
      setLoading(false)
      setSuccess(true)
    }, 600)
  }

  const switchToRegister = () => {
    onClose()
    // Small delay so the close animation plays before opening the register modal
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
              {success ? (
                <p className="auth-modal__success">{t('auth.loginSuccess')}</p>
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
