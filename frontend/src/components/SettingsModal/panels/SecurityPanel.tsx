import { useState } from 'react'
import { useLocale } from '../../../context/LocaleContext'
import { useAuth } from '../../../context/AuthContext'
import ForgotPasswordModal from './ForgotPasswordModal'

function maskEmail(email: string) {
  const [name, domain] = email.split('@')
  if (!domain) return email
  if (name.length <= 2) return `*@${domain}`
  const masked = name[0] + '*'.repeat(name.length - 2) + name[name.length - 1]
  return `${masked}@${domain}`
}

export default function SecurityPanel() {
  const { t } = useLocale()
  const { user } = useAuth()
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

  return (
    <div className="settings-panel">
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
