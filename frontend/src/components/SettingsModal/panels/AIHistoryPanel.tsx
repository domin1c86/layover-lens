import { useLocale } from '../../../context/LocaleContext'

export default function AIHistoryPanel() {
  const { t } = useLocale()
  return (
    <div className="settings-panel">
      <h2 className="settings-panel__title">{t('settings.menu.aiHistory')}</h2>
      <p className="settings-panel__placeholder">{t('settings.placeholder')}</p>
    </div>
  )
}
