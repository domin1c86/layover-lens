import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { useLocale } from '../../context/LocaleContext'
import { Icon } from '../../icons'
import { authApi, getApiErrorMessage } from '../../services/api'
import './AuthModals.css'

interface ForgotPasswordFlowModalProps {
  isOpen: boolean
  onClose: () => void
  onSwitchToRegister: (email: string) => void
  onSuccess: () => void
}

type Step = 'email' | 'notFound' | 'verify' | 'reset' | 'success'

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

export default function ForgotPasswordFlowModal({
  isOpen,
  onClose,
  onSwitchToRegister,
  onSuccess,
}: ForgotPasswordFlowModalProps) {
  const { lang, t } = useLocale()
  const [step, setStep] = useState<Step>('email')
  const [email, setEmail] = useState('')
  const [codeInput, setCodeInput] = useState('')
  const [resetToken, setResetToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [countdown, setCountdown] = useState(0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const isEnglish = lang === 'en'

  useEffect(() => {
    if (!isOpen) return
    setStep('email')
    setEmail('')
    setCodeInput('')
    setResetToken('')
    setNewPassword('')
    setConfirmPassword('')
    setCountdown(0)
    setError('')
    setLoading(false)
  }, [isOpen])

  useEffect(() => {
    if (countdown <= 0) return
    const timer = setTimeout(() => setCountdown((c) => c - 1), 1000)
    return () => clearTimeout(timer)
  }, [countdown])

  useEffect(() => {
    if (step !== 'success') return
    const timer = setTimeout(() => {
      onSuccess()
    }, 2000)
    return () => clearTimeout(timer)
  }, [step, onSuccess])

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

  const sendCode = async (targetEmail: string) => {
    const response = await authApi.sendForgotPasswordCode(targetEmail)
    setCountdown(response.expires_in_seconds)
    setError('')
  }

  const handleSendCode = async () => {
    setError('')
    const trimmed = email.trim()
    if (!trimmed) {
      setError(t('forgotPasswordFlow.emailEmpty'))
      return
    }
    if (!isValidEmail(trimmed)) {
      setError(t('forgotPasswordFlow.emailInvalid'))
      return
    }

    setLoading(true)
    try {
      const result = await authApi.checkForgotPasswordEmail(trimmed)
      if (!result.registered) {
        setStep('notFound')
        return
      }
      setEmail(trimmed)
      await sendCode(trimmed)
      setStep('verify')
    } catch (err) {
      setError(getApiErrorMessage(err, isEnglish ? 'Unable to send verification code.' : '验证码发送失败，请稍后重试。'))
    } finally {
      setLoading(false)
    }
  }

  const handleVerifySubmit = async () => {
    const code = codeInput.trim()
    if (!code) {
      setError(t('forgotPasswordFlow.codeMismatch'))
      return
    }

    setLoading(true)
    setError('')
    try {
      const result = await authApi.verifyForgotPasswordCode(email, code)
      if (!result.verified || !result.reset_token) {
        setError(t('forgotPasswordFlow.codeMismatch'))
        return
      }
      setResetToken(result.reset_token)
      setStep('reset')
    } catch (err) {
      setError(getApiErrorMessage(err, isEnglish ? 'Verification failed.' : '验证码验证失败，请稍后重试。'))
    } finally {
      setLoading(false)
    }
  }

  const handleResend = async () => {
    setLoading(true)
    try {
      await sendCode(email)
    } catch (err) {
      setError(getApiErrorMessage(err, isEnglish ? 'Unable to resend verification code.' : '重新发送失败，请稍后重试。'))
    } finally {
      setLoading(false)
    }
  }

  const handleResetSubmit = async () => {
    if (newPassword.length < 6) {
      setError(t('auth.passwordTooShort'))
      return
    }
    if (newPassword !== confirmPassword) {
      setError(t('auth.passwordMismatch'))
      return
    }

    setLoading(true)
    setError('')
    try {
      await authApi.resetForgotPassword(resetToken, newPassword)
      setStep('success')
    } catch (err) {
      setError(getApiErrorMessage(err, isEnglish ? 'Password reset failed.' : '密码重置失败，请稍后重试。'))
    } finally {
      setLoading(false)
    }
  }

  const handleRegisterYes = () => {
    onClose()
    setTimeout(() => onSwitchToRegister(email), 200)
  }

  const handleRegisterNo = () => {
    setError('')
    setStep('email')
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          key="forgot-pw-overlay"
          className="auth-modal__overlay"
          onClick={onClose}
          role="dialog"
          aria-modal="true"
          aria-label={t('forgotPasswordFlow.title')}
          variants={overlayVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          transition={{ duration: 0.2 }}
        >
          <motion.div
            key="forgot-pw-dialog"
            className="auth-modal__dialog"
            onClick={(e) => e.stopPropagation()}
            variants={dialogVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            transition={{ duration: 0.25, ease: 'easeOut' }}
          >
            <div className="auth-modal__header">
              <h3 className="auth-modal__title">{t('forgotPasswordFlow.title')}</h3>
              <button className="auth-modal__close" onClick={onClose} type="button" aria-label="Close">
                <Icon name="actions.closeEmoji" />
              </button>
            </div>

            <div className="auth-modal__body">
              {step === 'email' && (
                <>
                  <p className="forgot-modal__desc" style={{ margin: 0 }}>
                    {t('forgotPasswordFlow.emailDesc')}
                  </p>
                  <input
                    className="settings-panel__input"
                    type="email"
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); setError('') }}
                    placeholder={t('forgotPasswordFlow.emailPlaceholder')}
                    autoComplete="email"
                  />
                  {error && <p className="auth-modal__error">{error}</p>}
                  <button
                    className="settings-panel__btn settings-panel__btn--primary"
                    onClick={handleSendCode}
                    type="button"
                    disabled={loading}
                    style={{ width: '100%' }}
                  >
                    {loading ? t('forgotPasswordFlow.checking') : t('forgotPasswordFlow.sendCode')}
                  </button>
                </>
              )}

              {step === 'notFound' && (
                <>
                  <p className="auth-modal__error" style={{ textAlign: 'center', margin: 0 }}>
                    {t('forgotPasswordFlow.notFound')}
                  </p>
                  <p className="auth-modal__switch-text" style={{ textAlign: 'center', margin: 0 }}>
                    {t('forgotPasswordFlow.notFoundPrompt')}
                  </p>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      className="settings-panel__btn settings-panel__btn--primary"
                      onClick={handleRegisterYes}
                      type="button"
                      style={{ flex: 1 }}
                    >
                      {t('forgotPasswordFlow.registerYes')}
                    </button>
                    <button
                      className="settings-panel__btn settings-panel__btn--gray"
                      onClick={handleRegisterNo}
                      type="button"
                      style={{ flex: 1 }}
                    >
                      {t('forgotPasswordFlow.registerNo')}
                    </button>
                  </div>
                </>
              )}

              {step === 'verify' && (
                <>
                  <p className="forgot-modal__desc" style={{ margin: 0 }}>
                    {t('forgotPasswordFlow.codeSent').replace('{{email}}', email)}
                  </p>
                  <p className="settings-panel__hint" style={{ margin: 0 }}>
                    {isEnglish ? 'Beta code: 000000' : '内测验证码：000000'}
                  </p>
                  <input
                    className="settings-panel__input"
                    type="text"
                    value={codeInput}
                    onChange={(e) => { setCodeInput(e.target.value); setError('') }}
                    placeholder={t('forgotPasswordFlow.codePlaceholder')}
                    maxLength={12}
                  />
                  {error && <p className="auth-modal__error">{error}</p>}
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      className="settings-panel__btn settings-panel__btn--primary"
                      onClick={handleVerifySubmit}
                      type="button"
                      disabled={loading}
                      style={{ flex: 1 }}
                    >
                      {loading ? '...' : t('forgotPasswordFlow.verifyBtn')}
                    </button>
                    <button
                      className="settings-panel__btn settings-panel__btn--gray"
                      onClick={handleResend}
                      type="button"
                      disabled={loading || countdown > 0}
                      style={{ flex: 1 }}
                    >
                      {countdown > 0
                        ? `${t('forgotPasswordFlow.resend')} (${countdown}s)`
                        : t('forgotPasswordFlow.resend')}
                    </button>
                  </div>
                </>
              )}

              {step === 'reset' && (
                <>
                  <input
                    className="settings-panel__input"
                    type="password"
                    value={newPassword}
                    onChange={(e) => { setNewPassword(e.target.value); setError('') }}
                    placeholder={t('settings.forgotPassword.newPassword')}
                    autoComplete="new-password"
                  />
                  <input
                    className="settings-panel__input"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => { setConfirmPassword(e.target.value); setError('') }}
                    placeholder={t('settings.forgotPassword.confirmPassword')}
                    autoComplete="new-password"
                  />
                  {error && <p className="auth-modal__error">{error}</p>}
                  <button
                    className="settings-panel__btn settings-panel__btn--primary"
                    onClick={handleResetSubmit}
                    type="button"
                    disabled={loading}
                    style={{ width: '100%' }}
                  >
                    {loading ? '...' : t('settings.forgotPassword.titleReset')}
                  </button>
                </>
              )}

              {step === 'success' && (
                <p className="auth-modal__success">{t('settings.forgotPassword.successMessage')}</p>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
