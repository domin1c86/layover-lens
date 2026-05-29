import { useEffect, useState } from 'react'
import { useLocale } from '../../../context/LocaleContext'
import { Icon } from '../../../icons'

type Step = 'email' | 'verify' | 'reset' | 'success'

interface Props {
  isOpen: boolean
  onClose: () => void
  userEmail: string
  maskedEmail: string
}

function generateCode() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
  let code = ''
  for (let i = 0; i < 6; i++) {
    code += chars[Math.floor(Math.random() * chars.length)]
  }
  return code
}

export default function ForgotPasswordModal({ isOpen, onClose, userEmail, maskedEmail }: Props) {
  const { t } = useLocale()
  const [step, setStep] = useState<Step>('email')
  const [emailInput, setEmailInput] = useState('')
  const [codeInput, setCodeInput] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [code, setCode] = useState('')
  const [codeTime, setCodeTime] = useState(0)
  const [countdown, setCountdown] = useState(0)

  useEffect(() => {
    if (!isOpen) return
    setStep('email')
    setEmailInput('')
    setCodeInput('')
    setNewPassword('')
    setConfirmPassword('')
    setError('')
    setCode('')
    setCodeTime(0)
    setCountdown(0)
  }, [isOpen])

  useEffect(() => {
    if (countdown <= 0) return
    const timer = setTimeout(() => setCountdown((c) => c - 1), 1000)
    return () => clearTimeout(timer)
  }, [countdown])

  useEffect(() => {
    if (step === 'success') {
      const timer = setTimeout(() => onClose(), 3000)
      return () => clearTimeout(timer)
    }
  }, [step, onClose])

  const sendCode = () => {
    const newCode = generateCode()
    setCode(newCode)
    setCodeTime(Date.now())
    setCountdown(60)
    setError('')
    console.log('[模拟] 验证码已发送至邮箱:', userEmail, '验证码:', newCode)
  }

  const handleEmailSubmit = () => {
    const trimmed = emailInput.trim()
    if (!trimmed) {
      setError(t('settings.forgotPassword.emailEmpty') || '请输入内容')
      return
    }
    if (trimmed.toLowerCase() !== userEmail.toLowerCase()) {
      setError(t('settings.forgotPassword.emailMismatch') || '邮箱地址错误')
      return
    }
    sendCode()
    setStep('verify')
  }

  const handleVerifySubmit = () => {
    if (Date.now() - codeTime > 60000) {
      setError(t('settings.forgotPassword.codeExpired') || '验证码已过期')
      return
    }
    if (codeInput.trim().toUpperCase() !== code) {
      setError(t('settings.forgotPassword.codeMismatch') || '验证码不匹配')
      return
    }
    setError('')
    setStep('reset')
  }

  const handleResend = () => {
    sendCode()
  }

  const handleResetSubmit = () => {
    if (newPassword !== confirmPassword) {
      setError(t('settings.forgotPassword.passwordMismatch') || '两次输入的密码不一致')
      return
    }
    if (newPassword.length < 6) {
      setError(t('settings.forgotPassword.passwordTooShort') || '密码长度至少为6位')
      return
    }
    setError('')
    setStep('success')
  }

  if (!isOpen) return null

  return (
    <div className="forgot-modal__overlay" onClick={onClose}>
      <div className="forgot-modal__dialog" onClick={(e) => e.stopPropagation()}>
        <div className="forgot-modal__header">
          <h3 className="forgot-modal__title">
            {step === 'email' && (t('settings.forgotPassword.titleEmail') || '验证邮箱')}
            {step === 'verify' && (t('settings.forgotPassword.titleVerify') || '输入验证码')}
            {step === 'reset' && (t('settings.forgotPassword.titleReset') || '重置密码')}
            {step === 'success' && (t('settings.forgotPassword.titleSuccess') || '重置成功')}
          </h3>
          <button className="forgot-modal__close" onClick={onClose} type="button" aria-label="Close">
            <Icon name="actions.closeEmoji" />
          </button>
        </div>

        <div className="forgot-modal__body">
          {step === 'email' && (
            <>
              <p className="forgot-modal__desc">
                {(t('settings.forgotPassword.emailDesc') || '输入完整 {{email}} 邮箱地址以继续').replace('{{email}}', maskedEmail)}
              </p>
              <input
                className="settings-panel__input"
                type="email"
                value={emailInput}
                onChange={(e) => { setEmailInput(e.target.value); setError('') }}
                placeholder={t('settings.security.email') || '邮箱'}
              />
              {error && <p className="forgot-modal__error">{error}</p>}
              <button className="settings-panel__btn settings-panel__btn--primary" onClick={handleEmailSubmit} type="button">
                {t('settings.forgotPassword.sendCode') || '发送验证码'}
              </button>
            </>
          )}

          {step === 'verify' && (
            <>
              <p className="forgot-modal__desc">
                {(t('settings.forgotPassword.verifyDesc') || '验证码已发送至 {{email}}').replace('{{email}}', userEmail)}
              </p>
              <input
                className="settings-panel__input"
                type="text"
                value={codeInput}
                onChange={(e) => { setCodeInput(e.target.value); setError('') }}
                placeholder={t('settings.forgotPassword.codePlaceholder') || '请输入6位验证码'}
                maxLength={6}
              />
              {error && <p className="forgot-modal__error">{error}</p>}
              <div className="forgot-modal__actions">
                <button className="settings-panel__btn settings-panel__btn--primary" onClick={handleVerifySubmit} type="button">
                  {t('settings.security.confirm') || '确认'}
                </button>
                <button
                  className="settings-panel__btn settings-panel__btn--gray"
                  onClick={handleResend}
                  type="button"
                  disabled={countdown > 0}
                >
                  {countdown > 0
                    ? `${t('settings.forgotPassword.resend') || '重新发送'} (${countdown}s)`
                    : t('settings.forgotPassword.resend') || '重新发送'}
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
                placeholder={t('settings.forgotPassword.newPassword') || '新密码'}
              />
              <input
                className="settings-panel__input"
                type="password"
                value={confirmPassword}
                onChange={(e) => { setConfirmPassword(e.target.value); setError('') }}
                placeholder={t('settings.forgotPassword.confirmPassword') || '确认密码'}
              />
              {error && <p className="forgot-modal__error">{error}</p>}
              <button className="settings-panel__btn settings-panel__btn--primary" onClick={handleResetSubmit} type="button">
                {t('settings.security.confirm') || '确认'}
              </button>
            </>
          )}

          {step === 'success' && (
            <>
              <p className="forgot-modal__success">{t('settings.forgotPassword.successMessage') || '密码重置成功，3秒后自动关闭'}</p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
