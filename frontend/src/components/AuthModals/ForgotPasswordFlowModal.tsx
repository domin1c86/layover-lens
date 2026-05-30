import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { useLocale } from '../../context/LocaleContext'
import { Icon } from '../../icons'
import './AuthModals.css'

interface ForgotPasswordFlowModalProps {
  isOpen: boolean
  onClose: () => void
  onSwitchToRegister: (email: string) => void
  onSuccess: () => void
}

type Step = 'email' | 'notFound' | 'verify' | 'success'

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

function generateCode(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
  let code = ''
  for (let i = 0; i < 6; i++) {
    code += chars[Math.floor(Math.random() * chars.length)]
  }
  return code
}

/** Mock check: returns true if the email looks "registered" */
function mockCheckEmail(email: string): boolean {
  // Emails containing "new" or "test" are treated as unregistered for demo purposes
  const lower = email.toLowerCase()
  if (lower.includes('new') || lower.includes('test')) {
    return false
  }
  return true
}

export default function ForgotPasswordFlowModal({
  isOpen,
  onClose,
  onSwitchToRegister,
  onSuccess,
}: ForgotPasswordFlowModalProps) {
  const { t } = useLocale()
  const [step, setStep] = useState<Step>('email')
  const [email, setEmail] = useState('')
  const [codeInput, setCodeInput] = useState('')
  const [code, setCode] = useState('')
  const [codeTime, setCodeTime] = useState(0)
  const [countdown, setCountdown] = useState(0)
  const [error, setError] = useState('')
  const [checking, setChecking] = useState(false)

  useEffect(() => {
    if (!isOpen) return
    setStep('email')
    setEmail('')
    setCodeInput('')
    setCode('')
    setCodeTime(0)
    setCountdown(0)
    setError('')
    setChecking(false)
  }, [isOpen])

  useEffect(() => {
    if (countdown <= 0) return
    const timer = setTimeout(() => setCountdown((c) => c - 1), 1000)
    return () => clearTimeout(timer)
  }, [countdown])

  useEffect(() => {
    if (step === 'success') {
      const timer = setTimeout(() => {
        onSuccess()
      }, 2000)
      return () => clearTimeout(timer)
    }
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

  const sendCode = () => {
    const newCode = generateCode()
    setCode(newCode)
    setCodeTime(Date.now())
    setCountdown(60)
    setError('')
    console.log('[模拟] 忘记密码验证码已发送至:', email, '验证码:', newCode)
  }

  const handleSendCode = () => {
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

    setChecking(true)
    // Simulate server check delay
    setTimeout(() => {
      setChecking(false)
      if (mockCheckEmail(trimmed)) {
        // Registered — send code and go to verify step
        sendCode()
        setStep('verify')
      } else {
        // Not registered — show prompt
        setStep('notFound')
      }
    }, 1000)
  }

  const handleVerifySubmit = () => {
    if (Date.now() - codeTime > 60000) {
      setError(t('forgotPasswordFlow.codeExpired'))
      return
    }
    if (codeInput.trim().toUpperCase() !== code) {
      setError(t('forgotPasswordFlow.codeMismatch'))
      return
    }
    setError('')
    setStep('success')
  }

  const handleResend = () => {
    sendCode()
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
              {/* Step: email input */}
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
                    disabled={checking}
                    style={{ width: '100%' }}
                  >
                    {checking ? t('forgotPasswordFlow.checking') : t('forgotPasswordFlow.sendCode')}
                  </button>
                </>
              )}

              {/* Step: account not found */}
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

              {/* Step: verify code */}
              {step === 'verify' && (
                <>
                  <p className="forgot-modal__desc" style={{ margin: 0 }}>
                    {t('forgotPasswordFlow.codeSent').replace('{{email}}', email)}
                  </p>
                  <input
                    className="settings-panel__input"
                    type="text"
                    value={codeInput}
                    onChange={(e) => { setCodeInput(e.target.value); setError('') }}
                    placeholder={t('forgotPasswordFlow.codePlaceholder')}
                    maxLength={6}
                  />
                  {error && <p className="auth-modal__error">{error}</p>}
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      className="settings-panel__btn settings-panel__btn--primary"
                      onClick={handleVerifySubmit}
                      type="button"
                      style={{ flex: 1 }}
                    >
                      {t('forgotPasswordFlow.verifyBtn')}
                    </button>
                    <button
                      className="settings-panel__btn settings-panel__btn--gray"
                      onClick={handleResend}
                      type="button"
                      disabled={countdown > 0}
                      style={{ flex: 1 }}
                    >
                      {countdown > 0
                        ? `${t('forgotPasswordFlow.resend')} (${countdown}s)`
                        : t('forgotPasswordFlow.resend')}
                    </button>
                  </div>
                </>
              )}

              {/* Step: success */}
              {step === 'success' && (
                <p className="auth-modal__success">{t('forgotPasswordFlow.successMessage')}</p>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
