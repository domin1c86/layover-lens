import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocale } from '../../../context/LocaleContext'
import { useAuth } from '../../../context/AuthContext'
import { Icon } from '../../../icons'
import { authApi, getApiErrorMessage } from '../../../services/api'
import { getPasswordStrength, isValidEmail } from '../../../utils/security'
import AnimatedModal from '../../common/AnimatedModal'
import ForgotPasswordModal from './ForgotPasswordModal'
import type { EmailVerificationPurpose, SessionDuration } from '../../../types'

type PasswordCheckState = 'empty' | 'checking' | 'valid' | 'invalid'
type EmailDialog = 'verify-current' | 'change-email' | null
type ChangeEmailStep = 'confirm-old' | 'verify-code' | 'success'

function maskEmail(email: string) {
  const [name, domain] = email.split('@')
  if (!domain) return email
  if (name.length <= 2) return `*@${domain}`
  const masked = name[0] + '*'.repeat(name.length - 2) + name[name.length - 1]
  return `${masked}@${domain}`
}

function statusClass(state: 'neutral' | 'green' | 'orange' | 'red') {
  if (state === 'green') return 'verified'
  if (state === 'orange') return 'unverified'
  if (state === 'red') return 'invalid'
  return ''
}

function copy(lang: 'zh' | 'en') {
  return {
    sessionDuration: lang === 'en' ? 'Session duration' : '登录保持时长',
    sessionHint: lang === 'en'
      ? 'This applies the next time you sign in. The current session will not be extended automatically.'
      : '该设置将在下次登录或注册时生效，当前登录不会被自动延长。',
    durations: {
      day: lang === 'en' ? 'One day' : '一天',
      week: lang === 'en' ? 'One week' : '一周',
      month: lang === 'en' ? 'One month' : '一月',
      half_year: lang === 'en' ? 'Six months' : '半年',
      year: lang === 'en' ? 'One year' : '一年',
      forever: lang === 'en' ? 'Forever' : '永久',
    } satisfies Record<SessionDuration, string>,
    verifyEmail: lang === 'en' ? 'Verify email' : '验证邮箱',
    resetEmail: lang === 'en' ? 'Reset email' : '重置邮箱',
    confirm: lang === 'en' ? 'Confirm' : '确认',
    cancel: lang === 'en' ? 'Cancel' : '取消',
    betaCode: lang === 'en' ? 'Beta code: 000000' : '内测验证码：000000',
    codePlaceholder: lang === 'en' ? 'Enter verification code' : '请输入验证码',
    resend: lang === 'en' ? 'Resend' : '重新发送',
    currentVerifyTitle: lang === 'en' ? 'Verify current email' : '验证当前邮箱',
    currentVerifyDesc: lang === 'en'
      ? 'A verification code has been sent to {{email}}. Enter the code to mark this email as verified.'
      : '验证码已发送至 {{email}}。输入验证码后，该邮箱将标记为已验证。',
    changeEmailOldTitle: lang === 'en' ? 'Confirm current email' : '确认旧邮箱',
    changeEmailOldDesc: lang === 'en'
      ? 'Enter your current email address before a code is sent to the new email.'
      : '请先输入当前旧邮箱名称，确认后会向新邮箱发送验证码。',
    currentEmailPlaceholder: lang === 'en' ? 'Current email' : '当前旧邮箱',
    changeEmailCodeTitle: lang === 'en' ? 'Verify new email' : '验证新邮箱',
    changeEmailCodeDesc: lang === 'en'
      ? 'A verification code has been sent to {{email}}. Enter it to finish changing your email.'
      : '验证码已发送至 {{email}}。输入验证码后完成邮箱重置。',
    emailVerified: lang === 'en' ? 'Email verified.' : '邮箱验证完成。',
    emailChanged: lang === 'en' ? 'Email updated.' : '邮箱重置完成。',
    codeInvalid: lang === 'en' ? 'The verification code is incorrect or expired.' : '验证码错误或已过期。',
    sendFailed: lang === 'en' ? 'Unable to send verification code.' : '验证码发送失败，请稍后重试。',
    oldEmailMismatch: lang === 'en' ? 'Current email does not match.' : '旧邮箱名称不匹配。',
    newEmailInvalid: lang === 'en' ? 'Enter a valid new email.' : '请输入有效的新邮箱。',
    passwordUpdated: lang === 'en' ? 'Password updated.' : '密码已修改。',
    passwordFailed: lang === 'en' ? 'Unable to update password.' : '密码修改失败，请稍后重试。',
    confirmPasswordPlaceholder: lang === 'en' ? 'Confirm new password' : '确认新密码',
    hidePassword: lang === 'en' ? 'Hide password' : '隐藏密码',
    showPassword: lang === 'en' ? 'Show password' : '显示密码',
  }
}

export default function SecurityPanel() {
  const { lang, t } = useLocale()
  const texts = copy(lang)
  const { user, sessionDuration, setSessionDuration, refreshUser } = useAuth()
  const [email, setEmail] = useState(user?.email || '')
  const [emailEditing, setEmailEditing] = useState(false)
  const [emailDialog, setEmailDialog] = useState<EmailDialog>(null)
  const [changeEmailStep, setChangeEmailStep] = useState<ChangeEmailStep>('confirm-old')
  const [oldEmailInput, setOldEmailInput] = useState('')
  const [emailCode, setEmailCode] = useState('')
  const [emailCountdown, setEmailCountdown] = useState(0)
  const [emailError, setEmailError] = useState('')
  const [emailSuccess, setEmailSuccess] = useState('')
  const [emailLoading, setEmailLoading] = useState(false)
  const emailEditRef = useRef<HTMLDivElement | null>(null)

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showCurrentPassword, setShowCurrentPassword] = useState(false)
  const [showNewPassword, setShowNewPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [currentPasswordStatus, setCurrentPasswordStatus] = useState<PasswordCheckState>('empty')
  const [passwordMessage, setPasswordMessage] = useState('')
  const [passwordLoading, setPasswordLoading] = useState(false)
  const [showForgotModal, setShowForgotModal] = useState(false)

  const currentEmail = user?.email || ''
  const targetEmail = email.trim()

  useEffect(() => {
    setEmail(user?.email || '')
  }, [user?.email])

  useEffect(() => {
    if (!emailEditing) return
    const handlePointerDown = (event: MouseEvent) => {
      if (emailEditRef.current?.contains(event.target as Node)) return
      setEmailEditing(false)
      setEmail(currentEmail)
    }
    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [currentEmail, emailEditing])

  useEffect(() => {
    if (emailCountdown <= 0) return
    const timer = setTimeout(() => setEmailCountdown((value) => Math.max(0, value - 1)), 1000)
    return () => clearTimeout(timer)
  }, [emailCountdown])

  useEffect(() => {
    setPasswordMessage('')
    if (!currentPassword) {
      setCurrentPasswordStatus('empty')
      return
    }
    setCurrentPasswordStatus('checking')
    const timer = setTimeout(async () => {
      try {
        const valid = await authApi.checkPassword(currentPassword)
        setCurrentPasswordStatus(valid ? 'valid' : 'invalid')
      } catch {
        setCurrentPasswordStatus('invalid')
      }
    }, 350)
    return () => clearTimeout(timer)
  }, [currentPassword])

  const durationOptions = useMemo<Array<{ value: SessionDuration; label: string }>>(
    () => ([
      { value: 'day', label: texts.durations.day },
      { value: 'week', label: texts.durations.week },
      { value: 'month', label: texts.durations.month },
      { value: 'half_year', label: texts.durations.half_year },
      { value: 'year', label: texts.durations.year },
      { value: 'forever', label: texts.durations.forever },
    ]),
    [texts.durations]
  )

  const isEmailVerified = user?.email_verified ?? false
  const newPasswordStrength = getPasswordStrength(newPassword, currentPassword)
  const newPasswordLight = newPasswordStrength === 'empty'
    ? 'neutral'
    : newPasswordStrength === 'weak'
      ? 'red'
      : newPasswordStrength === 'medium'
        ? 'orange'
        : 'green'
  const confirmPasswordLight = !confirmPassword ? 'neutral' : confirmPassword === newPassword ? 'green' : 'red'
  const currentPasswordLight = currentPasswordStatus === 'valid'
    ? 'green'
    : currentPasswordStatus === 'invalid'
      ? 'orange'
      : 'neutral'
  const canUpdatePassword = currentPasswordStatus === 'valid' && newPasswordLight !== 'red' && confirmPasswordLight === 'green'

  const resetEmailDialog = () => {
    setEmailDialog(null)
    setChangeEmailStep('confirm-old')
    setOldEmailInput('')
    setEmailCode('')
    setEmailCountdown(0)
    setEmailError('')
    setEmailSuccess('')
    setEmailLoading(false)
  }

  const sendEmailCode = useCallback(async (mail: string, purpose: EmailVerificationPurpose) => {
    const response = await authApi.sendEmailVerificationCode(mail, purpose)
    setEmailCountdown(response.expires_in_seconds)
    setEmailCode('')
    setEmailError('')
  }, [])

  const openVerifyCurrentEmail = async () => {
    setEmailDialog('verify-current')
    setEmailCode('')
    setEmailError('')
    setEmailSuccess('')
    setEmailLoading(true)
    try {
      await sendEmailCode(currentEmail, 'verify_current')
    } catch (err) {
      setEmailError(getApiErrorMessage(err, texts.sendFailed))
    } finally {
      setEmailLoading(false)
    }
  }

  const startEmailReset = () => {
    setEmail('')
    setEmailEditing(true)
  }

  const confirmEmailReset = () => {
    if (!isValidEmail(targetEmail) || targetEmail.toLowerCase() === currentEmail.toLowerCase()) {
      setEmailError(texts.newEmailInvalid)
      return
    }
    setEmailDialog('change-email')
    setChangeEmailStep('confirm-old')
    setOldEmailInput('')
    setEmailCode('')
    setEmailError('')
    setEmailSuccess('')
  }

  const confirmOldEmailAndSendCode = async () => {
    if (oldEmailInput.trim().toLowerCase() !== currentEmail.toLowerCase()) {
      setEmailError(texts.oldEmailMismatch)
      return
    }
    setEmailLoading(true)
    setEmailError('')
    try {
      await sendEmailCode(targetEmail, 'change_email')
      setChangeEmailStep('verify-code')
    } catch (err) {
      setEmailError(getApiErrorMessage(err, texts.sendFailed))
    } finally {
      setEmailLoading(false)
    }
  }

  const verifyEmailCode = async () => {
    const purpose: EmailVerificationPurpose = emailDialog === 'change-email' ? 'change_email' : 'verify_current'
    const mail = emailDialog === 'change-email' ? targetEmail : currentEmail
    setEmailLoading(true)
    setEmailError('')
    try {
      const result = await authApi.verifyEmailVerificationCode(mail, emailCode.trim(), purpose)
      if (!result.verified || !result.verification_token) {
        setEmailError(texts.codeInvalid)
        return
      }
      if (emailDialog === 'change-email') {
        await authApi.updateEmail(currentEmail, targetEmail, result.verification_token)
        setEmailSuccess(texts.emailChanged)
        setEmailEditing(false)
      } else {
        await authApi.verifyCurrentEmail(result.verification_token)
        setEmailSuccess(texts.emailVerified)
      }
      await refreshUser()
      setTimeout(resetEmailDialog, 900)
    } catch (err) {
      setEmailError(getApiErrorMessage(err, texts.codeInvalid))
    } finally {
      setEmailLoading(false)
    }
  }

  const resendDialogCode = async () => {
    setEmailLoading(true)
    setEmailError('')
    try {
      await sendEmailCode(
        emailDialog === 'change-email' ? targetEmail : currentEmail,
        emailDialog === 'change-email' ? 'change_email' : 'verify_current'
      )
    } catch (err) {
      setEmailError(getApiErrorMessage(err, texts.sendFailed))
    } finally {
      setEmailLoading(false)
    }
  }

  const handleUpdatePassword = async () => {
    if (!canUpdatePassword) return
    setPasswordLoading(true)
    setPasswordMessage('')
    try {
      await authApi.updatePassword(currentPassword, newPassword)
      setPasswordMessage(texts.passwordUpdated)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setCurrentPasswordStatus('empty')
    } catch (err) {
      setPasswordMessage(getApiErrorMessage(err, texts.passwordFailed))
    } finally {
      setPasswordLoading(false)
    }
  }

  const passwordInput = (
    value: string,
    onChange: (value: string) => void,
    placeholder: string,
    visible: boolean,
    setVisible: (value: boolean) => void,
    autocomplete: string
  ) => (
    <div className="auth-modal__input-wrap settings-panel__password-wrap">
      <input
        className="settings-panel__input"
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        autoComplete={autocomplete}
      />
      <button
        className="auth-modal__toggle-pw"
        type="button"
        onClick={() => setVisible(!visible)}
        aria-label={visible ? texts.hidePassword : texts.showPassword}
      >
        <Icon name={visible ? 'actions.eyeOff' : 'actions.eyeOn'} size={16} />
      </button>
    </div>
  )

  const emailDialogTitle = emailDialog === 'change-email'
    ? changeEmailStep === 'confirm-old' ? texts.changeEmailOldTitle : texts.changeEmailCodeTitle
    : texts.currentVerifyTitle
  const emailDialogDesc = emailDialog === 'change-email'
    ? changeEmailStep === 'confirm-old'
      ? texts.changeEmailOldDesc
      : texts.changeEmailCodeDesc.replace('{{email}}', targetEmail)
    : texts.currentVerifyDesc.replace('{{email}}', maskEmail(currentEmail))

  return (
    <div className="settings-panel">
      <div className="settings-panel__section">
        <div className="settings-panel__label">{texts.sessionDuration}</div>
        <div className="settings-panel__options">
          {durationOptions.map((option) => (
            <button
              key={option.value}
              className={`settings-panel__option ${sessionDuration === option.value ? 'active' : ''}`}
              type="button"
              onClick={() => setSessionDuration(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <p className="settings-panel__hint">{texts.sessionHint}</p>
      </div>

      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.security.email')}</div>
        <div className="settings-panel__row" ref={emailEditRef}>
          <div className={`settings-panel__status-pill ${statusClass(isEmailVerified ? 'green' : 'orange')}`} />
          <input
            className="settings-panel__input"
            type="email"
            value={emailEditing ? email : maskEmail(currentEmail)}
            onChange={(event) => { setEmail(event.target.value); setEmailError('') }}
            readOnly={!emailEditing}
            placeholder={emailEditing ? t('auth.emailPlaceholder') : undefined}
          />
          {!isEmailVerified && !emailEditing && (
            <button
              className="settings-panel__btn settings-panel__btn--gray"
              onClick={openVerifyCurrentEmail}
              type="button"
            >
              {texts.verifyEmail}
            </button>
          )}
          <button
            className="settings-panel__btn settings-panel__btn--gray"
            onClick={emailEditing ? confirmEmailReset : startEmailReset}
            type="button"
          >
            {emailEditing ? texts.confirm : texts.resetEmail}
          </button>
        </div>
        {emailError && !emailDialog && <p className="forgot-modal__error">{emailError}</p>}
      </div>

      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.security.changePasswordTitle')}</div>
        <div className="settings-panel__row settings-panel__row--stack">
          <div className="settings-panel__row">
            <div className={`settings-panel__status-pill ${statusClass(currentPasswordLight)}`} />
            {passwordInput(
              currentPassword,
              setCurrentPassword,
              t('settings.security.passwordCurrentPlaceholder'),
              showCurrentPassword,
              setShowCurrentPassword,
              'current-password'
            )}
          </div>
          <div className="settings-panel__row">
            <div className={`settings-panel__status-pill ${statusClass(newPasswordLight)}`} />
            {passwordInput(
              newPassword,
              setNewPassword,
              t('settings.security.passwordNewPlaceholder'),
              showNewPassword,
              setShowNewPassword,
              'new-password'
            )}
          </div>
          <div className="settings-panel__row">
            <div className={`settings-panel__status-pill ${statusClass(confirmPasswordLight)}`} />
            {passwordInput(
              confirmPassword,
              setConfirmPassword,
              texts.confirmPasswordPlaceholder,
              showConfirmPassword,
              setShowConfirmPassword,
              'new-password'
            )}
          </div>
          {passwordMessage && <p className="settings-panel__hint">{passwordMessage}</p>}
          <button
            className={`settings-panel__btn ${canUpdatePassword ? 'settings-panel__btn--primary' : 'settings-panel__btn--gray'}`}
            type="button"
            onClick={handleUpdatePassword}
            disabled={!canUpdatePassword || passwordLoading}
          >
            {passwordLoading ? '...' : t('settings.security.confirm')}
          </button>
        </div>
        <button className="settings-panel__link" onClick={() => setShowForgotModal(true)} type="button">
          {t('settings.security.forgotPassword')}
        </button>
      </div>

      <AnimatedModal
        isOpen={emailDialog !== null}
        overlayClassName="forgot-modal__overlay"
        dialogClassName="forgot-modal__dialog"
        ariaLabel={emailDialogTitle}
        onClose={resetEmailDialog}
      >
        <div className="forgot-modal__header">
          <h3 className="forgot-modal__title">{emailDialogTitle}</h3>
          <button className="forgot-modal__close" onClick={resetEmailDialog} type="button" aria-label="Close">
            <Icon name="actions.closeEmoji" />
          </button>
        </div>
        <div className="forgot-modal__body">
          <p className="forgot-modal__desc">{emailDialogDesc}</p>
          {emailDialog === 'change-email' && changeEmailStep === 'confirm-old' ? (
            <>
              <input
                className="settings-panel__input"
                type="email"
                value={oldEmailInput}
                onChange={(event) => { setOldEmailInput(event.target.value); setEmailError('') }}
                placeholder={texts.currentEmailPlaceholder}
              />
              {emailError && <p className="forgot-modal__error">{emailError}</p>}
              <button
                className="settings-panel__btn settings-panel__btn--primary"
                type="button"
                onClick={confirmOldEmailAndSendCode}
                disabled={emailLoading}
              >
                {emailLoading ? '...' : texts.confirm}
              </button>
            </>
          ) : (
            <>
              <p className="settings-panel__hint" style={{ margin: 0 }}>{texts.betaCode}</p>
              <input
                className="settings-panel__input"
                type="text"
                value={emailCode}
                onChange={(event) => { setEmailCode(event.target.value); setEmailError('') }}
                placeholder={texts.codePlaceholder}
                maxLength={12}
              />
              {emailSuccess && <p className="forgot-modal__success">{emailSuccess}</p>}
              {emailError && <p className="forgot-modal__error">{emailError}</p>}
              <div className="forgot-modal__actions">
                <button
                  className="settings-panel__btn settings-panel__btn--primary"
                  type="button"
                  onClick={verifyEmailCode}
                  disabled={emailLoading || !emailCode.trim()}
                >
                  {emailLoading ? '...' : texts.confirm}
                </button>
                <button
                  className="settings-panel__btn settings-panel__btn--gray"
                  type="button"
                  disabled={emailLoading || emailCountdown > 0}
                  onClick={resendDialogCode}
                >
                  {emailCountdown > 0 ? `${texts.resend} (${emailCountdown}s)` : texts.resend}
                </button>
              </div>
            </>
          )}
        </div>
      </AnimatedModal>

      <ForgotPasswordModal
        isOpen={showForgotModal}
        onClose={() => setShowForgotModal(false)}
        userEmail={currentEmail}
        maskedEmail={maskEmail(currentEmail)}
      />
    </div>
  )
}
