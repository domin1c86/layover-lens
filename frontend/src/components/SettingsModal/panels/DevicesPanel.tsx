import { useAuth } from '../../../context/AuthContext'
import { useLocale } from '../../../context/LocaleContext'

export default function DevicesPanel() {
  const { t } = useLocale()
  const { isLoggedIn } = useAuth()

  return (
    <div className="settings-panel">
      <div className="settings-panel__section">
        {isLoggedIn ? (
          <p className="settings-panel__hint" style={{ textAlign: 'center', padding: '24px 0' }}>
            {t('settings.devices.noDevices')}
          </p>
        ) : (
          <p className="settings-panel__hint" style={{ textAlign: 'center', padding: '24px 0' }}>
            {t('settings.devices.noDevices')}
          </p>
        )}
      </div>
    </div>
  )
}
