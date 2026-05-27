import { useLocale } from '../../../context/LocaleContext'

export default function AccountPanel() {
  const { t } = useLocale()
  return (
    <div className="settings-panel">
      <h2 className="settings-panel__title">{t('settings.menu.account')}</h2>
      <p className="settings-panel__placeholder">{t('settings.placeholder')}</p>
    </div>
  )
}
