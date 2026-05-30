import { useLocale } from '../../../context/LocaleContext'
import { useTheme } from '../../../context/ThemeContext'

export default function AppearancePanel() {
  const { t } = useLocale()
  const { isDark, toggleTheme } = useTheme()

  return (
    <div className="settings-panel">
      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.appearance.theme')}</div>
        <div className="settings-panel__options">
          <button
            className={`settings-panel__option ${!isDark ? 'active' : ''}`}
            onClick={() => isDark && toggleTheme()}
            type="button"
          >
            {t('settings.appearance.themeLight')}
          </button>
          <button
            className={`settings-panel__option ${isDark ? 'active' : ''}`}
            onClick={() => !isDark && toggleTheme()}
            type="button"
          >
            {t('settings.appearance.themeDark')}
          </button>
        </div>
      </div>

      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.appearance.language')}</div>
        <div className="settings-panel__options">
          <LangOption code="zh" label={t('settings.appearance.languageZh')} />
          <LangOption code="en" label={t('settings.appearance.languageEn')} />
        </div>
      </div>
    </div>
  )
}

function LangOption({ code, label }: { code: 'zh' | 'en'; label: string }) {
  const { lang, setLang } = useLocale()
  return (
    <button
      className={`settings-panel__option ${lang === code ? 'active' : ''}`}
      onClick={() => setLang(code)}
      type="button"
    >
      {label}
    </button>
  )
}
