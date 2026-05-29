import { useState } from 'react'
import { useLocale } from '../../../context/LocaleContext'
import { useAuth } from '../../../context/AuthContext'

export default function AccountPanel() {
  const { t } = useLocale()
  const { user } = useAuth()
  const [nickname, setNickname] = useState(user?.username || '')

  return (
    <div className="settings-panel">
      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.account.avatar')}</div>
        <div className="settings-panel__avatar-row">
          <div className="settings-panel__avatar">
            {user ? (
              <span style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: '100%', height: '100%', fontSize: '24px', fontWeight: 600,
                color: '#fff', background: 'var(--primary)', borderRadius: '50%',
              }}>
                {(user.username || user.email || '?')[0].toUpperCase()}
              </span>
            ) : null}
          </div>
          <button className="settings-panel__btn settings-panel__btn--gray" type="button">
            {t('settings.account.changeAvatar')}
          </button>
        </div>
      </div>

      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.account.nickname')}</div>
        <div className="settings-panel__row">
          <input
            className="settings-panel__input"
            type="text"
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            placeholder={t('settings.account.nicknamePlaceholder')}
          />
          <button className="settings-panel__btn settings-panel__btn--gray" type="button">
            {t('settings.account.saveNickname')}
          </button>
        </div>
      </div>

      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.account.username')}</div>
        <div className="settings-panel__row">
          <input
            className="settings-panel__input"
            type="text"
            value={user?.username || ''}
            readOnly
          />
        </div>
        <p className="settings-panel__hint">{t('settings.account.usernameDesc')}</p>
      </div>
    </div>
  )
}
