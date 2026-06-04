import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { useLocale } from '../../../context/LocaleContext'
import { useAuth } from '../../../context/AuthContext'
import { Icon } from '../../../icons'
import { authApi, getApiErrorMessage } from '../../../services/api'
import { getPasswordStrength, isValidEmail } from '../../../utils/security'
import AnimatedModal from '../../common/AnimatedModal'
import ForgotPasswordModal from './ForgotPasswordModal'
import type { EmailVerificationPurpose, SessionDuration } from '../../../types'

type PasswordCheckState = 'empty' | 'checking' | 'valid' | 'invalid'
type SignalState = 'neutral' | 'green' | 'orange' | 'red'
type EmailDialog = 'verify-current' | 'change-email' | null
type ChangeEmailStep = 'confirm-old' | 'verify-code'
type TotpDialog = 'setup-password' | 'setup-code' | 'disable' | null
type TotpSetupMethod = 'qr' | 'secret'

function normalizeTotpCode(value: string) {
  return value.replace(/\s/g, '').replace(/\D/g, '').slice(0, 6)
}

function maskEmail(email: string) {
  const [name, domain] = email.split('@')
  if (!domain) return email
  if (name.length <= 2) return `*@${domain}`
  const masked = name[0] + '*'.repeat(name.length - 2) + name[name.length - 1]
  return `${masked}@${domain}`
}

function statusClass(state: SignalState) {
  if (state === 'green') return 'verified'
  if (state === 'orange') return 'unverified'
  if (state === 'red') return 'invalid'
  return ''
}

function StatusPill({ state, label }: { state: SignalState; label: string }) {
  return (
    <span className="settings-panel__status-wrap" tabIndex={0} aria-label={label}>
      <span className={`settings-panel__status-pill ${statusClass(state)}`} aria-hidden="true" />
      <span className="settings-panel__status-tooltip" role="tooltip">{label}</span>
    </span>
  )
}

export default function SecurityPanel() {
  const { t } = useLocale()
  const { user, sessionDuration, setSessionDuration, refreshUser } = useAuth()
  const [email, setEmail] = useState(user?.email || '')
  const [pendingNewEmail, setPendingNewEmail] = useState('')
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
  const [passwordError, setPasswordError] = useState('')
  const [passwordLoading, setPasswordLoading] = useState(false)
  const [passwordSuccessOpen, setPasswordSuccessOpen] = useState(false)
  const [showForgotModal, setShowForgotModal] = useState(false)
  const [sessionUpdating, setSessionUpdating] = useState<SessionDuration | null>(null)
  const [sessionError, setSessionError] = useState('')
  const [totpDialog, setTotpDialog] = useState<TotpDialog>(null)
  const [totpPassword, setTotpPassword] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [totpSecret, setTotpSecret] = useState('')
  const [totpProvisioningUri, setTotpProvisioningUri] = useState('')
  const [totpSetupMethod, setTotpSetupMethod] = useState<TotpSetupMethod>('qr')
  const [totpError, setTotpError] = useState('')
  const [totpLoading, setTotpLoading] = useState(false)

  const currentEmail = user?.email || ''
  const targetEmail = email.trim()

  useEffect(() => {
    setEmail(user?.email || '')
  }, [user?.email])

  useEffect(() => {
    if (!emailEditing || emailDialog) return
    const handlePointerDown = (event: MouseEvent) => {
      if (emailEditRef.current?.contains(event.target as Node)) return
      setEmailEditing(false)
      setEmail(currentEmail)
      setPendingNewEmail('')
      setEmailError('')
    }
    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [currentEmail, emailDialog, emailEditing])

  useEffect(() => {
    if (emailCountdown <= 0) return
    const timer = setTimeout(() => setEmailCountdown((value) => Math.max(0, value - 1)), 1000)
    return () => clearTimeout(timer)
  }, [emailCountdown])

  useEffect(() => {
    setPasswordError('')
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
      { value: 'day', label: t('settings.security.sessionDurationDay') },
      { value: 'week', label: t('settings.security.sessionDurationWeek') },
      { value: 'month', label: t('settings.security.sessionDurationMonth') },
      { value: 'half_year', label: t('settings.security.sessionDurationHalfYear') },
      { value: 'year', label: t('settings.security.sessionDurationYear') },
      { value: 'forever', label: t('settings.security.sessionDurationForever') },
    ]),
    [t]
  )

  const isEmailVerified = user?.email_verified ?? false
  const canConfirmEmailReset = emailEditing
    && isValidEmail(targetEmail)
    && targetEmail.toLowerCase() !== currentEmail.toLowerCase()
  const newPasswordStrength = getPasswordStrength(newPassword, currentPassword)
  const newPasswordLight: SignalState = newPasswordStrength === 'empty'
    ? 'neutral'
    : newPasswordStrength === 'weak'
      ? 'red'
      : newPasswordStrength === 'medium'
        ? 'orange'
        : 'green'
  const confirmPasswordLight: SignalState = !confirmPassword ? 'neutral' : confirmPassword === newPassword ? 'green' : 'red'
  const currentPasswordLight: SignalState = currentPasswordStatus === 'valid'
    ? 'green'
    : currentPasswordStatus === 'invalid'
      ? 'orange'
      : 'neutral'
  const canUpdatePassword = currentPasswordStatus === 'valid' && newPasswordLight !== 'red' && confirmPasswordLight === 'green'
  const canEnableTotp = totpCode.length === 6
  const canDisableTotp = totpPassword.trim().length > 0 && totpCode.length === 6

  const emailStatusText = isEmailVerified
    ? t('settings.security.statusEmailVerified')
    : t('settings.security.statusEmailUnverified')
  const currentPasswordStatusText = {
    empty: t('settings.security.statusCurrentPasswordEmpty'),
    checking: t('settings.security.statusCurrentPasswordChecking'),
    valid: t('settings.security.statusCurrentPasswordValid'),
    invalid: t('settings.security.statusCurrentPasswordInvalid'),
  }[currentPasswordStatus]
  const newPasswordStatusText = !newPassword
    ? t('settings.security.statusNewPasswordEmpty')
    : currentPassword && newPassword === currentPassword
      ? t('settings.security.statusNewPasswordSame')
      : newPasswordStrength === 'weak'
        ? t('settings.security.statusNewPasswordWeak')
        : newPasswordStrength === 'medium'
          ? t('settings.security.statusNewPasswordMedium')
          : t('settings.security.statusNewPasswordStrong')
  const confirmPasswordStatusText = !confirmPassword
    ? t('settings.security.statusConfirmPasswordEmpty')
    : confirmPassword === newPassword
      ? t('settings.security.statusConfirmPasswordValid')
      : t('settings.security.statusConfirmPasswordInvalid')

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
      setEmailError(getApiErrorMessage(err, t('settings.security.sendFailed')))
    } finally {
      setEmailLoading(false)
    }
  }

  const startEmailReset = () => {
    setEmail('')
    setPendingNewEmail('')
    setEmailEditing(true)
    setEmailError('')
  }

  const confirmEmailReset = () => {
    if (!isValidEmail(targetEmail) || targetEmail.toLowerCase() === currentEmail.toLowerCase()) {
      setEmailError(t('settings.security.newEmailInvalid'))
      return
    }
    setPendingNewEmail(targetEmail)
    setEmailDialog('change-email')
    setChangeEmailStep('confirm-old')
    setOldEmailInput('')
    setEmailCode('')
    setEmailError('')
    setEmailSuccess('')
  }

  const confirmOldEmailAndSendCode = async () => {
    if (oldEmailInput.trim().toLowerCase() !== currentEmail.toLowerCase()) {
      setEmailError(t('settings.security.oldEmailMismatch'))
      return
    }
    setEmailLoading(true)
    setEmailError('')
    try {
      await sendEmailCode(pendingNewEmail, 'change_email')
      setChangeEmailStep('verify-code')
    } catch (err) {
      setEmailError(getApiErrorMessage(err, t('settings.security.sendFailed')))
    } finally {
      setEmailLoading(false)
    }
  }

  const verifyEmailCode = async () => {
    const isChangeEmail = emailDialog === 'change-email'
    const purpose: EmailVerificationPurpose = isChangeEmail ? 'change_email' : 'verify_current'
    const mail = isChangeEmail ? pendingNewEmail : currentEmail
    setEmailLoading(true)
    setEmailError('')
    try {
      const result = await authApi.verifyEmailVerificationCode(mail, emailCode.trim(), purpose)
      if (!result.verified || !result.verification_token) {
        setEmailError(t('settings.security.codeInvalid'))
        return
      }
      if (isChangeEmail) {
        await authApi.updateEmail(currentEmail, pendingNewEmail, result.verification_token)
        setEmailSuccess(t('settings.security.emailChanged'))
        setEmailEditing(false)
      } else {
        await authApi.verifyCurrentEmail(result.verification_token)
        setEmailSuccess(t('settings.security.emailVerifiedDone'))
      }
      await refreshUser()
      setTimeout(resetEmailDialog, 900)
    } catch (err) {
      setEmailError(getApiErrorMessage(err, t('settings.security.codeInvalid')))
    } finally {
      setEmailLoading(false)
    }
  }

  const resendDialogCode = async () => {
    setEmailLoading(true)
    setEmailError('')
    try {
      await sendEmailCode(
        emailDialog === 'change-email' ? pendingNewEmail : currentEmail,
        emailDialog === 'change-email' ? 'change_email' : 'verify_current'
      )
    } catch (err) {
      setEmailError(getApiErrorMessage(err, t('settings.security.sendFailed')))
    } finally {
      setEmailLoading(false)
    }
  }

  const handleSessionDurationChange = async (duration: SessionDuration) => {
    if (duration === sessionDuration || sessionUpdating) return
    setSessionUpdating(duration)
    setSessionError('')
    try {
      await setSessionDuration(duration)
    } catch (err) {
      setSessionError(getApiErrorMessage(err, t('settings.security.sessionUpdateFailed')))
    } finally {
      setSessionUpdating(null)
    }
  }

  const closePasswordSuccess = () => {
    setPasswordSuccessOpen(false)
    setCurrentPassword('')
    setNewPassword('')
    setConfirmPassword('')
    setCurrentPasswordStatus('empty')
  }

  const resetTotpDialog = () => {
    setTotpDialog(null)
    setTotpPassword('')
    setTotpCode('')
    setTotpSecret('')
    setTotpProvisioningUri('')
    setTotpSetupMethod('qr')
    setTotpError('')
    setTotpLoading(false)
  }

  const beginTotpSetup = async () => {
    if (!totpPassword) return
    setTotpLoading(true)
    setTotpError('')
    try {
      const result = await authApi.setupTotp(totpPassword)
      setTotpSecret(result.secret)
      setTotpProvisioningUri(result.provisioning_uri)
      setTotpSetupMethod('qr')
      setTotpCode('')
      setTotpDialog('setup-code')
    } catch (err) {
      setTotpError(getApiErrorMessage(err, t('settings.security.totpSetupFailed')))
    } finally {
      setTotpLoading(false)
    }
  }

  const enableTotp = async () => {
    if (!canEnableTotp) return
    setTotpLoading(true)
    setTotpError('')
    try {
      await authApi.enableTotp(totpCode.trim())
      await refreshUser()
      resetTotpDialog()
    } catch (err) {
      setTotpError(getApiErrorMessage(err, t('settings.security.totpCodeInvalid')))
    } finally {
      setTotpLoading(false)
    }
  }

  const disableTotp = async () => {
    if (!canDisableTotp) return
    setTotpLoading(true)
    setTotpError('')
    try {
      await authApi.disableTotp(totpPassword, totpCode.trim())
      await refreshUser()
      resetTotpDialog()
    } catch (err) {
      setTotpError(getApiErrorMessage(err, t('settings.security.totpDisableFailed')))
    } finally {
      setTotpLoading(false)
    }
  }

  const openTotpDialog = () => {
    setTotpPassword('')
    setTotpCode('')
    setTotpSecret('')
    setTotpProvisioningUri('')
    setTotpSetupMethod('qr')
    setTotpError('')
    setTotpDialog(user?.totp_enabled ? 'disable' : 'setup-password')
  }

  const handleUpdatePassword = async () => {
    if (!canUpdatePassword) return
    setPasswordLoading(true)
    setPasswordError('')
    try {
      await authApi.updatePassword(currentPassword, newPassword)
      setPasswordSuccessOpen(true)
    } catch (err) {
      setPasswordError(getApiErrorMessage(err, t('settings.security.passwordFailed')))
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
        aria-label={visible ? t('settings.security.hidePassword') : t('settings.security.showPassword')}
      >
        <Icon name={visible ? 'actions.eyeOff' : 'actions.eyeOn'} size={16} />
      </button>
    </div>
  )

  const emailDialogTitle = emailDialog === 'change-email'
    ? changeEmailStep === 'confirm-old'
      ? t('settings.security.changeEmailOldTitle')
      : t('settings.security.changeEmailCodeTitle')
    : t('settings.security.currentVerifyTitle')
  const emailDialogDesc = emailDialog === 'change-email'
    ? changeEmailStep === 'confirm-old'
      ? t('settings.security.changeEmailOldDesc')
      : t('settings.security.changeEmailCodeDesc', { email: pendingNewEmail })
    : t('settings.security.currentVerifyDesc', { email: maskEmail(currentEmail) })

  return (
    <div className="settings-panel">
      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.security.sessionDuration')}</div>
        <div className="settings-panel__options">
          {durationOptions.map((option) => (
            <button
              key={option.value}
              className={`settings-panel__option ${sessionDuration === option.value ? 'active' : ''}`}
              type="button"
              onClick={() => void handleSessionDurationChange(option.value)}
              disabled={sessionUpdating !== null}
            >
              {sessionUpdating === option.value ? '...' : option.label}
            </button>
          ))}
        </div>
        <p className="settings-panel__hint">{t('settings.security.sessionHint')}</p>
        {sessionError && <p className="forgot-modal__error">{sessionError}</p>}
      </div>

      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.security.email')}</div>
        <div className="settings-panel__row" ref={emailEditRef}>
          <StatusPill state={isEmailVerified ? 'green' : 'orange'} label={emailStatusText} />
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
              {t('settings.security.verifyEmail')}
            </button>
          )}
          <button
            className={`settings-panel__btn ${emailEditing && canConfirmEmailReset ? 'settings-panel__btn--password-ready' : 'settings-panel__btn--gray'} ${emailEditing ? '' : 'settings-panel__btn--email-reset'}`}
            onClick={emailEditing ? confirmEmailReset : startEmailReset}
            type="button"
            disabled={emailEditing && !canConfirmEmailReset}
          >
            {emailEditing ? t('settings.security.confirm') : t('settings.security.emailReset')}
          </button>
        </div>
        {emailError && !emailDialog && <p className="forgot-modal__error">{emailError}</p>}
      </div>

      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.security.totpTitle')}</div>
        <div className="settings-panel__row">
          <StatusPill
            state={user?.totp_enabled ? 'green' : 'orange'}
            label={user?.totp_enabled ? t('settings.security.totpEnabledStatus') : t('settings.security.totpDisabledStatus')}
          />
          <div className="settings-panel__input settings-panel__totp-summary">
            {user?.totp_enabled ? t('settings.security.totpEnabledDesc') : t('settings.security.totpDisabledDesc')}
          </div>
          <button
            className="settings-panel__btn settings-panel__btn--gray settings-panel__btn--totp-action"
            type="button"
            onClick={openTotpDialog}
          >
            {user?.totp_enabled ? t('settings.security.totpDisable') : t('settings.security.totpEnable')}
          </button>
        </div>
        {emailError && !emailDialog && <p className="forgot-modal__error">{emailError}</p>}
      </div>

      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.security.changePasswordTitle')}</div>
        <div className="settings-panel__row settings-panel__row--stack">
          <div className="settings-panel__row">
            <StatusPill state={currentPasswordLight} label={currentPasswordStatusText} />
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
            <StatusPill state={newPasswordLight} label={newPasswordStatusText} />
            {passwordInput(
              newPassword,
              setNewPassword,
              t('settings.security.passwordNewPlaceholder'),
              showNewPassword,
              setShowNewPassword,
              'new-password'
            )}
          </div>
          <p className="settings-panel__hint settings-panel__password-hint">
            {t('settings.security.passwordCompositionHint')}
          </p>
          <div className="settings-panel__row">
            <StatusPill state={confirmPasswordLight} label={confirmPasswordStatusText} />
            {passwordInput(
              confirmPassword,
              setConfirmPassword,
              t('settings.security.passwordConfirmPlaceholder'),
              showConfirmPassword,
              setShowConfirmPassword,
              'new-password'
            )}
          </div>
          {passwordError && <p className="forgot-modal__error">{passwordError}</p>}
          <button
            className={`settings-panel__btn ${canUpdatePassword ? 'settings-panel__btn--password-ready' : 'settings-panel__btn--gray'}`}
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
          <button className="forgot-modal__close" onClick={resetEmailDialog} type="button" aria-label={t('settings.security.close')}>
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
                placeholder={t('settings.security.currentEmailPlaceholder')}
              />
              {emailError && <p className="forgot-modal__error">{emailError}</p>}
              <button
                className="settings-panel__btn settings-panel__btn--primary"
                type="button"
                onClick={confirmOldEmailAndSendCode}
                disabled={emailLoading}
              >
                {emailLoading ? '...' : t('settings.security.confirm')}
              </button>
            </>
          ) : (
            <>
              <p className="settings-panel__hint" style={{ margin: 0 }}>{t('settings.security.betaCode')}</p>
              <input
                className="settings-panel__input"
                type="text"
                value={emailCode}
                onChange={(event) => { setEmailCode(event.target.value); setEmailError('') }}
                placeholder={t('settings.security.codePlaceholder')}
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
                  {emailLoading ? '...' : t('settings.security.confirm')}
                </button>
                <button
                  className="settings-panel__btn settings-panel__btn--gray"
                  type="button"
                  disabled={emailLoading || emailCountdown > 0}
                  onClick={resendDialogCode}
                >
                  {emailCountdown > 0 ? `${t('settings.security.resend')} (${emailCountdown}s)` : t('settings.security.resend')}
                </button>
              </div>
            </>
          )}
        </div>
      </AnimatedModal>

      <AnimatedModal
        isOpen={passwordSuccessOpen}
        overlayClassName="forgot-modal__overlay"
        dialogClassName="forgot-modal__dialog"
        ariaLabel={t('settings.security.passwordSuccessTitle')}
        onClose={closePasswordSuccess}
      >
        <div className="forgot-modal__header">
          <h3 className="forgot-modal__title">{t('settings.security.passwordSuccessTitle')}</h3>
          <button className="forgot-modal__close" onClick={closePasswordSuccess} type="button" aria-label={t('settings.security.close')}>
            <Icon name="actions.closeEmoji" />
          </button>
        </div>
        <div className="forgot-modal__body">
          <p className="forgot-modal__success">{t('settings.security.passwordSuccessDesc')}</p>
          <button
            className="settings-panel__btn settings-panel__btn--primary"
            type="button"
            onClick={closePasswordSuccess}
          >
            {t('settings.security.confirm')}
          </button>
        </div>
      </AnimatedModal>

      <AnimatedModal
        isOpen={totpDialog !== null}
        overlayClassName="forgot-modal__overlay"
        dialogClassName="forgot-modal__dialog"
        ariaLabel={t('settings.security.totpTitle')}
        onClose={resetTotpDialog}
      >
        <div className="forgot-modal__header">
          <h3 className="forgot-modal__title">
            {totpDialog === 'disable' ? t('settings.security.totpDisableTitle') : t('settings.security.totpSetupTitle')}
          </h3>
          <button className="forgot-modal__close" onClick={resetTotpDialog} type="button" aria-label={t('settings.security.close')}>
            <Icon name="actions.closeEmoji" />
          </button>
        </div>
        <div className="forgot-modal__body">
          {totpDialog === 'setup-password' && (
            <>
              <p className="forgot-modal__desc">{t('settings.security.totpPasswordDesc')}</p>
              <input
                className="settings-panel__input"
                type="password"
                autoComplete="current-password"
                value={totpPassword}
                onChange={(event) => { setTotpPassword(event.target.value); setTotpError('') }}
                placeholder={t('settings.security.passwordCurrentPlaceholder')}
              />
              {totpError && <p className="forgot-modal__error">{totpError}</p>}
              <button
                className={`settings-panel__btn ${totpPassword.trim() ? 'settings-panel__btn--password-ready' : 'settings-panel__btn--gray'}`}
                type="button"
                onClick={beginTotpSetup}
                disabled={!totpPassword.trim() || totpLoading}
              >
                {totpLoading ? '...' : t('settings.security.confirm')}
              </button>
            </>
          )}
          {totpDialog === 'setup-code' && (
            <>
              {totpSetupMethod === 'qr' ? (
                <>
                  <p className="forgot-modal__desc">{t('settings.security.totpQrSetupDesc')}</p>
                  <div className="settings-panel__totp-qr">
                    <QRCodeSVG
                      value={totpProvisioningUri}
                      size={196}
                      level="M"
                      marginSize={2}
                      title={t('settings.security.totpQrCodeLabel')}
                    />
                  </div>
                  <button
                    className="settings-panel__totp-switch"
                    type="button"
                    onClick={() => setTotpSetupMethod('secret')}
                  >
                    {t('settings.security.totpUseSecret')}
                  </button>
                </>
              ) : (
                <>
                  <p className="forgot-modal__desc">{t('settings.security.totpSetupDesc')}</p>
                  <div className="settings-panel__totp-secret">{totpSecret}</div>
                  <button
                    className="settings-panel__btn settings-panel__btn--gray settings-panel__btn--totp-action"
                    type="button"
                    onClick={() => void navigator.clipboard?.writeText(totpSecret)}
                  >
                    {t('settings.security.totpCopySecret')}
                  </button>
                  <button
                    className="settings-panel__totp-switch"
                    type="button"
                    onClick={() => setTotpSetupMethod('qr')}
                  >
                    {t('settings.security.totpUseQr')}
                  </button>
                </>
              )}
              <input
                className="settings-panel__input"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={totpCode}
                onChange={(event) => { setTotpCode(normalizeTotpCode(event.target.value)); setTotpError('') }}
                placeholder={t('settings.security.totpCodePlaceholder')}
              />
              {totpError && <p className="forgot-modal__error">{totpError}</p>}
              <button
                className={`settings-panel__btn ${canEnableTotp ? 'settings-panel__btn--password-ready' : 'settings-panel__btn--gray'}`}
                type="button"
                onClick={enableTotp}
                disabled={!canEnableTotp || totpLoading}
              >
                {totpLoading ? '...' : t('settings.security.totpVerifyEnable')}
              </button>
            </>
          )}
          {totpDialog === 'disable' && (
            <>
              <p className="forgot-modal__desc">{t('settings.security.totpDisableDesc')}</p>
              <input
                className="settings-panel__input"
                type="password"
                autoComplete="current-password"
                value={totpPassword}
                onChange={(event) => { setTotpPassword(event.target.value); setTotpError('') }}
                placeholder={t('settings.security.passwordCurrentPlaceholder')}
              />
              <input
                className="settings-panel__input"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={totpCode}
                onChange={(event) => { setTotpCode(normalizeTotpCode(event.target.value)); setTotpError('') }}
                placeholder={t('settings.security.totpCodePlaceholder')}
              />
              {totpError && <p className="forgot-modal__error">{totpError}</p>}
              <button
                className={`settings-panel__btn ${canDisableTotp ? 'settings-panel__btn--password-ready' : 'settings-panel__btn--gray'}`}
                type="button"
                onClick={disableTotp}
                disabled={!canDisableTotp || totpLoading}
              >
                {totpLoading ? '...' : t('settings.security.totpDisable')}
              </button>
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
