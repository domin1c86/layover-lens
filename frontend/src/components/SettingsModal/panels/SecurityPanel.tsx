import { useState } from 'react'
import { useLocale } from '../../../context/LocaleContext'
import { useAuth } from '../../../context/AuthContext'
import ForgotPasswordModal from './ForgotPasswordModal'
import type { SessionDuration } from '../../../types'

function maskEmail(email: string) {
  const [name, domain] = email.split('@')
  if (!domain) return email
  if (name.length <= 2) return `*@${domain}`
  const masked = name[0] + '*'.repeat(name.length - 2) + name[name.length - 1]
  return `${masked}@${domain}`
}

export default function SecurityPanel() {
  const { lang, t } = useLocale()
  const { user, sessionDuration, setSessionDuration } = useAuth()
  const [email, setEmail] = useState(user?.email || '')
  const [emailEditing, setEmailEditing] = useState(false)
  const [isEmailVerified] = useState(!!user)

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [showForgotModal, setShowForgotModal] = useState(false)

  const handleEmailAction = () => {
    if (emailEditing) {
      setEmailEditing(false)
    } else {
      setEmailEditing(true)
    }
  }

  const handleForgot = () => {
    setShowForgotModal(true)
  }

  const durationOptions: Array<{ value: SessionDuration; label: string }> = [
    { value: 'day', label: lang === 'en' ? 'One day' : '一天' },
    { value: 'week', label: lang === 'en' ? 'One week' : '一周' },
    { value: 'month', label: lang === 'en' ? 'One month' : '一月' },
    { value: 'half_year', label: lang === 'en' ? 'Six months' : '半年' },
    { value: 'year', label: lang === 'en' ? 'One year' : '一年' },
    { value: 'forever', label: lang === 'en' ? 'Forever' : '永久' },
  ]

  return (
    <div className="settings-panel">
      <div className="settings-panel__section">
        <div className="settings-panel__label">
          {lang === 'en' ? 'Session duration' : '登录保持时长'}
        </div>
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
        <p className="settings-panel__hint">
          {lang === 'en'
            ? 'This applies the next time you sign in. The current session will not be extended automatically.'
            : '该设置将在下次登录或注册时生效，当前登录不会被自动延长。'}
        </p>
      </div>

      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.security.email')}</div>
        <div className="settings-panel__row">
          <div className={`settings-panel__status-pill ${isEmailVerified ? 'verified' : 'unverified'}`} />
          <input
            className="settings-panel__input"
            type="email"
            value={emailEditing ? email : maskEmail(email)}
            onChange={(e) => setEmail(e.target.value)}
            readOnly={!emailEditing}
          />
          <button
            className="settings-panel__btn settings-panel__btn--gray"
            onClick={handleEmailAction}
            type="button"
          >
            {emailEditing ? t('settings.security.emailConfirm') : t('settings.security.emailReset')}
          </button>
        </div>
      </div>

      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.security.changePasswordTitle')}</div>
        <div className="settings-panel__row settings-panel__row--stack">
          <div className="settings-panel__row">
            <div className={`settings-panel__status-pill ${currentPassword ? 'verified' : 'unverified'}`} />
            <input
              className="settings-panel__input"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder={t('settings.security.passwordCurrentPlaceholder')}
            />
          </div>
          <div className="settings-panel__row">
            <div className={`settings-panel__status-pill ${
              newPassword === '' ? '' : newPassword.length >= 6 ? 'verified' : 'invalid'
            }`} />
            <input
              className="settings-panel__input"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder={t('settings.security.passwordNewPlaceholder')}
            />
          </div>
          <button className="settings-panel__btn settings-panel__btn--gray" type="button">
            {t('settings.security.confirm')}
          </button>
        </div>
        <button className="settings-panel__link" onClick={handleForgot} type="button">
          {t('settings.security.forgotPassword')}
        </button>
      </div>

      <ForgotPasswordModal
        isOpen={showForgotModal}
        onClose={() => setShowForgotModal(false)}
        userEmail={email}
        maskedEmail={maskEmail(email)}
      />
    </div>
  )
}
