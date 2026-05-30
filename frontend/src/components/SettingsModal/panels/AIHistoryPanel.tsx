import { useState } from 'react'
import { useLocale } from '../../../context/LocaleContext'

const RETENTION_OPTIONS = [
  { key: 'days7', value: 7 },
  { key: 'days30', value: 30 },
  { key: 'days90', value: 90 },
  { key: 'days180', value: 180 },
  { key: 'forever', value: -1 },
]

export default function AIHistoryPanel() {
  const { t } = useLocale()
  const [searchRetention, setSearchRetention] = useState(30)
  const [chatRetention, setChatRetention] = useState(30)

  return (
    <div className="settings-panel">
      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.aiHistory.searchRetention')}</div>
        <div className="settings-panel__options">
          {RETENTION_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              className={`settings-panel__option ${searchRetention === opt.value ? 'active' : ''}`}
              onClick={() => setSearchRetention(opt.value)}
              type="button"
            >
              {t(`settings.aiHistory.${opt.key}`)}
            </button>
          ))}
        </div>
      </div>

      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.aiHistory.chatRetention')}</div>
        <div className="settings-panel__options">
          {RETENTION_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              className={`settings-panel__option ${chatRetention === opt.value ? 'active' : ''}`}
              onClick={() => setChatRetention(opt.value)}
              type="button"
            >
              {t(`settings.aiHistory.${opt.key}`)}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
