import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { useLocale } from '../../context/LocaleContext'
import { useAuth } from '../../context/AuthContext'
import { Icon } from '../../icons'
import { authApi, getApiErrorMessage } from '../../services/api'
import type { SessionDuration } from '../../types'
import './AuthModals.css'

interface RegisterModalProps {
  isOpen: boolean
  onClose: () => void
  onSwitchToLogin: () => void
  prefillEmail?: string
}

type CodeStatus = 'idle' | 'pending' | 'valid' | 'invalid'

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

function text(lang: 'zh' | 'en') {
  return {
    verificationLabel: lang === 'en' ? 'Email code' : '邮箱验证',
    verificationPlaceholder: lang === 'en' ? 'Enter verification code' : '请输入验证码',
    sendCode: lang === 'en' ? 'Send code' : '发送验证码',
    resendCode: lang === 'en' ? 'Resend' : '重新发送',
    betaCode: lang === 'en' ? 'Beta code: 000000' : '内测验证码：000000',
    codeRequired: lang === 'en' ? 'Please verify your email before registering.' : '请先完成邮箱验证码验证。',
    codeInvalid: lang === 'en' ? 'The email verification code is incorrect or expired.' : '邮箱验证码错误或已过期。',
    sendFailed: lang === 'en' ? 'Unable to send verification code.' : '验证码发送失败，请稍后重试。',
    verifyFailed: lang === 'en' ? 'Verification failed. Please try again.' : '验证码校验失败，请稍后重试。',
    close: lang === 'en' ? 'Close' : '关闭',
    hidePassword: lang === 'en' ? 'Hide password' : '隐藏密码',
    showPassword: lang === 'en' ? 'Show password' : '显示密码',
    registerFailed: lang === 'en' ? 'Registration failed. Please try again.' : '注册失败，请稍后重试。',
  }
}

export default function RegisterModal({ isOpen, onClose, onSwitchToLogin, prefillEmail }: RegisterModalProps) {
  const { lang, t } = useLocale()
  const copy = text(lang)
  const { register } = useAuth()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [emailCode, setEmailCode] = useState('')
  const [emailVerificationToken, setEmailVerificationToken] = useState('')
  const [codeStatus, setCodeStatus] = useState<CodeStatus>('idle')
  const [codeExpiresAt, setCodeExpiresAt] = useState<number | null>(null)
  const [countdown, setCountdown] = useState(0)
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [sendingCode, setSendingCode] = useState(false)

  useEffect(() => {
    if (!isOpen) return
    setUsername('')
    setEmail(prefillEmail || '')
    setEmailCode('')
    setEmailVerificationToken('')
    setCodeStatus('idle')
    setCodeExpiresAt(null)
    setCountdown(0)
    setPassword('')
    setConfirmPassword('')
    setShowPassword(false)
    setShowConfirmPassword(false)
    setError('')
    setSuccessMessage('')
    setLoading(false)
    setSendingCode(false)
  }, [isOpen, prefillEmail])

  useEffect(() => {
    if (!successMessage) return
    const timer = setTimeout(() => {
      onClose()
    }, 4500)
    return () => clearTimeout(timer)
  }, [successMessage, onClose])

  useEffect(() => {
    if (countdown <= 0) return
    const timer = setTimeout(() => setCountdown((value) => Math.max(0, value - 1)), 1000)
    return () => clearTimeout(timer)
  }, [countdown])

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

  useEffect(() => {
    const trimmedEmail = email.trim()
    const trimmedCode = emailCode.trim()
    setEmailVerificationToken('')
    if (!trimmedCode) {
      setCodeStatus('idle')
      return
    }
    if (!codeExpiresAt || Date.now() > codeExpiresAt) {
      setCodeStatus('pending')
      return
    }
    const timer = setTimeout(async () => {
      try {
        const result = await authApi.verifyEmailVerificationCode(trimmedEmail, trimmedCode, 'register')
        if (result.verified && result.verification_token) {
          setEmailVerificationToken(result.verification_token)
          setCodeStatus('valid')
        } else {
          setCodeStatus('invalid')
        }
      } catch {
        setCodeStatus('invalid')
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [email, emailCode, codeExpiresAt])

  const resetEmailVerification = (nextEmail: string) => {
    setEmail(nextEmail)
    setEmailCode('')
    setEmailVerificationToken('')
    setCodeStatus('idle')
    setCodeExpiresAt(null)
    setCountdown(0)
    setError('')
  }

  const handleSendCode = async () => {
    const trimmedEmail = email.trim()
    if (!isValidEmail(trimmedEmail)) {
      setError(t('auth.emailInvalid'))
      return
    }
    setSendingCode(true)
    setError('')
    try {
      const result = await authApi.sendEmailVerificationCode(trimmedEmail, 'register')
      setCodeExpiresAt(Date.now() + result.expires_in_seconds * 1000)
      setCountdown(result.expires_in_seconds)
      setEmailCode('')
      setEmailVerificationToken('')
      setCodeStatus('idle')
    } catch (err) {
      setError(getApiErrorMessage(err, copy.sendFailed))
    } finally {
      setSendingCode(false)
    }
  }

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

    if (!emailVerificationToken || codeStatus !== 'valid') {
      setError(codeStatus === 'invalid' ? copy.codeInvalid : copy.codeRequired)
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
      const result = await register(trimmedEmail, trimmedUsername, password, emailVerificationToken)
      setSuccessMessage(successText(result.sessionDuration, lang))
    } catch (err) {
      setError(getApiErrorMessage(err, copy.registerFailed))
    } finally {
      setLoading(false)
    }
  }

  const switchToLogin = () => {
    onClose()
    setTimeout(() => onSwitchToLogin(), 200)
  }

  const verificationStatus = (() => {
    if (!emailCode.trim()) return null
    if (codeStatus === 'valid') return <span className="auth-modal__code-status valid">✓</span>
    if (codeStatus === 'invalid') return <span className="auth-modal__code-status invalid">×</span>
    return <span className="auth-modal__code-status pending">?</span>
  })()

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
              <button className="auth-modal__close" onClick={onClose} type="button" aria-label={copy.close}>
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
                      onChange={(e) => resetEmailVerification(e.target.value)}
                      placeholder={t('auth.emailPlaceholder')}
                      autoComplete="email"
                    />
                  </div>

                  <div className="auth-modal__field">
                    <label className="auth-modal__label">{copy.verificationLabel}</label>
                    <div className="auth-modal__code-row">
                      <div className="auth-modal__input-wrap">
                        <input
                          className="settings-panel__input"
                          type="text"
                          value={emailCode}
                          onChange={(e) => { setEmailCode(e.target.value); setError('') }}
                          placeholder={copy.verificationPlaceholder}
                          maxLength={12}
                        />
                        {verificationStatus}
                      </div>
                      <button
                        className="settings-panel__btn settings-panel__btn--gray auth-modal__code-btn"
                        type="button"
                        onClick={handleSendCode}
                        disabled={sendingCode || loading || !isValidEmail(email.trim()) || countdown > 0}
                      >
                        {sendingCode ? '...' : countdown > 0 ? `${copy.resendCode} (${countdown}s)` : copy.sendCode}
                      </button>
                    </div>
                    {codeExpiresAt && <p className="settings-panel__hint" style={{ margin: '6px 0 0' }}>{copy.betaCode}</p>}
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
                        aria-label={showPassword ? copy.hidePassword : copy.showPassword}
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
                        aria-label={showConfirmPassword ? copy.hidePassword : copy.showPassword}
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
