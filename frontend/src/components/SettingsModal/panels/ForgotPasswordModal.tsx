import { useEffect, useState } from 'react'
import { useLocale } from '../../../context/LocaleContext'
import { Icon } from '../../../icons'
import { authApi, getApiErrorMessage } from '../../../services/api'
import AnimatedModal from '../../common/AnimatedModal'

type Step = 'email' | 'verify' | 'reset' | 'success'

interface Props {
  isOpen: boolean
  onClose: () => void
  userEmail: string
  maskedEmail: string
}

export default function ForgotPasswordModal({ isOpen, onClose, userEmail, maskedEmail }: Props) {
  const { lang, t } = useLocale()
  const [step, setStep] = useState<Step>('email')
  const [emailInput, setEmailInput] = useState('')
  const [codeInput, setCodeInput] = useState('')
  const [resetToken, setResetToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [countdown, setCountdown] = useState(0)
  const [loading, setLoading] = useState(false)

  const isEnglish = lang === 'en'

  useEffect(() => {
    if (!isOpen) return
    setStep('email')
    setEmailInput('')
    setCodeInput('')
    setResetToken('')
    setNewPassword('')
    setConfirmPassword('')
    setError('')
    setCountdown(0)
    setLoading(false)
  }, [isOpen])

  useEffect(() => {
    if (countdown <= 0) return
    const timer = setTimeout(() => setCountdown((c) => c - 1), 1000)
    return () => clearTimeout(timer)
  }, [countdown])

  useEffect(() => {
    if (step !== 'success') return
    const timer = setTimeout(() => onClose(), 3000)
    return () => clearTimeout(timer)
  }, [step, onClose])

  const sendCode = async () => {
    const response = await authApi.sendForgotPasswordCode(userEmail)
    setCountdown(response.expires_in_seconds)
    setError('')
  }

  const handleEmailSubmit = async () => {
    const trimmed = emailInput.trim()
    if (!trimmed) {
      setError(t('settings.forgotPassword.emailEmpty'))
      return
    }
    if (trimmed.toLowerCase() !== userEmail.toLowerCase()) {
      setError(t('settings.forgotPassword.emailMismatch'))
      return
    }

    setLoading(true)
    try {
      await sendCode()
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
      setError(t('settings.forgotPassword.codeMismatch'))
      return
    }

    setLoading(true)
    setError('')
    try {
      const result = await authApi.verifyForgotPasswordCode(userEmail, code)
      if (!result.verified || !result.reset_token) {
        setError(t('settings.forgotPassword.codeMismatch'))
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
      await sendCode()
    } catch (err) {
      setError(getApiErrorMessage(err, isEnglish ? 'Unable to resend verification code.' : '重新发送失败，请稍后重试。'))
    } finally {
      setLoading(false)
    }
  }

  const handleResetSubmit = async () => {
    if (newPassword !== confirmPassword) {
      setError(t('settings.forgotPassword.passwordMismatch'))
      return
    }
    if (newPassword.length < 6) {
      setError(t('settings.forgotPassword.passwordTooShort'))
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

  return (
    <AnimatedModal
      isOpen={isOpen}
      overlayClassName="forgot-modal__overlay"
      dialogClassName="forgot-modal__dialog"
      ariaLabel={t('settings.forgotPassword.titleEmail')}
      onClose={onClose}
    >
        <div className="forgot-modal__header">
          <h3 className="forgot-modal__title">
            {step === 'email' && t('settings.forgotPassword.titleEmail')}
            {step === 'verify' && t('settings.forgotPassword.titleVerify')}
            {step === 'reset' && t('settings.forgotPassword.titleReset')}
            {step === 'success' && t('settings.forgotPassword.titleSuccess')}
          </h3>
          <button className="forgot-modal__close" onClick={onClose} type="button" aria-label="Close">
            <Icon name="actions.closeEmoji" />
          </button>
        </div>

        <div className="forgot-modal__body">
          {step === 'email' && (
            <>
              <p className="forgot-modal__desc">
                {t('settings.forgotPassword.emailDesc').replace('{{email}}', maskedEmail)}
              </p>
              <input
                className="settings-panel__input"
                type="email"
                value={emailInput}
                onChange={(e) => { setEmailInput(e.target.value); setError('') }}
                placeholder={t('settings.security.email')}
              />
              {error && <p className="forgot-modal__error">{error}</p>}
              <button
                className="settings-panel__btn settings-panel__btn--primary"
                onClick={handleEmailSubmit}
                type="button"
                disabled={loading}
              >
                {loading ? '...' : t('settings.forgotPassword.sendCode')}
              </button>
            </>
          )}

          {step === 'verify' && (
            <>
              <p className="forgot-modal__desc">
                {t('settings.forgotPassword.verifyDesc').replace('{{email}}', userEmail)}
              </p>
              <p className="settings-panel__hint" style={{ margin: 0 }}>
                {isEnglish ? 'Beta code: 000000' : '内测验证码：000000'}
              </p>
              <input
                className="settings-panel__input"
                type="text"
                value={codeInput}
                onChange={(e) => { setCodeInput(e.target.value); setError('') }}
                placeholder={t('settings.forgotPassword.codePlaceholder')}
                maxLength={12}
              />
              {error && <p className="forgot-modal__error">{error}</p>}
              <div className="forgot-modal__actions">
                <button
                  className="settings-panel__btn settings-panel__btn--primary"
                  onClick={handleVerifySubmit}
                  type="button"
                  disabled={loading}
                >
                  {loading ? '...' : t('settings.security.confirm')}
                </button>
                <button
                  className="settings-panel__btn settings-panel__btn--gray"
                  onClick={handleResend}
                  type="button"
                  disabled={loading || countdown > 0}
                >
                  {countdown > 0
                    ? `${t('settings.forgotPassword.resend')} (${countdown}s)`
                    : t('settings.forgotPassword.resend')}
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
              {error && <p className="forgot-modal__error">{error}</p>}
              <button
                className="settings-panel__btn settings-panel__btn--primary"
                onClick={handleResetSubmit}
                type="button"
                disabled={loading}
              >
                {loading ? '...' : t('settings.security.confirm')}
              </button>
            </>
          )}

          {step === 'success' && (
            <p className="forgot-modal__success">{t('settings.forgotPassword.successMessage')}</p>
          )}
        </div>
    </AnimatedModal>
  )
}
