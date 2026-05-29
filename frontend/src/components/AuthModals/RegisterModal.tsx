import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { useLocale } from '../../context/LocaleContext'
import { useAuth } from '../../context/AuthContext'
import { Icon } from '../../icons'
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

export default function RegisterModal({ isOpen, onClose, onSwitchToLogin, prefillEmail }: RegisterModalProps) {
  const { t } = useLocale()
  const { register } = useAuth()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
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
    setSuccess(false)
    setLoading(false)
  }, [isOpen, prefillEmail])

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
    // Mock register — replace with real API call when backend is ready
    console.log('[模拟] 注册:', { username: trimmedUsername, email: trimmedEmail, password })
    setTimeout(() => {
      register(trimmedEmail, trimmedUsername)
      setLoading(false)
      setSuccess(true)
    }, 600)
  }

  const switchToLogin = () => {
    onClose()
    // Small delay so the close animation plays before opening the login modal
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
              {success ? (
                <p className="auth-modal__success">{t('auth.registerSuccess')}</p>
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
