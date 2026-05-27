import { useLocale } from '../../../context/LocaleContext'

export default function AppearancePanel() {
  const { t } = useLocale()
  return (
    <div className="settings-panel">
      <h2 className="settings-panel__title">{t('settings.menu.appearance')}</h2>
      <p className="settings-panel__placeholder">{t('settings.placeholder')}</p>
    </div>
  )
}
