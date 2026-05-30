import { useLocale } from '../../context/LocaleContext'

export type SettingsTab = 'account' | 'security' | 'appearance' | 'aiHistory' | 'import' | 'devices'

interface NavMenuProps {
  activeTab: SettingsTab
  onChange: (tab: SettingsTab) => void
  disabledTabs?: Set<SettingsTab>
  disabledHint?: string
}

const TABS: { key: SettingsTab; labelKey: string }[] = [
  { key: 'account', labelKey: 'settings.menu.account' },
  { key: 'security', labelKey: 'settings.menu.security' },
  { key: 'appearance', labelKey: 'settings.menu.appearance' },
  { key: 'aiHistory', labelKey: 'settings.menu.aiHistory' },
  { key: 'import', labelKey: 'settings.menu.import' },
  { key: 'devices', labelKey: 'settings.menu.devices' },
]

export default function NavMenu({ activeTab, onChange, disabledTabs, disabledHint }: NavMenuProps) {
  const { t } = useLocale()

  return (
    <nav className="settings-nav" aria-label="Settings navigation">
      <div className="settings-nav__desktop">
        {TABS.map((tab) => {
          const isDisabled = disabledTabs?.has(tab.key) ?? false
          return (
            <button
              key={tab.key}
              className={`settings-nav__item ${activeTab === tab.key ? 'active' : ''} ${isDisabled ? 'disabled' : ''}`}
              onClick={() => !isDisabled && onChange(tab.key)}
              type="button"
              disabled={isDisabled}
              title={isDisabled ? (disabledHint || t('settings.menu.disabledHint')) : undefined}
            >
              {t(tab.labelKey)}
            </button>
          )
        })}
      </div>
      <div className="settings-nav__mobile">
        {TABS.map((tab) => {
          const isDisabled = disabledTabs?.has(tab.key) ?? false
          return (
            <button
              key={tab.key}
              className={`settings-nav__mobile-item ${activeTab === tab.key ? 'active' : ''} ${isDisabled ? 'disabled' : ''}`}
              onClick={() => !isDisabled && onChange(tab.key)}
              type="button"
              disabled={isDisabled}
              title={isDisabled ? (disabledHint || t('settings.menu.disabledHint')) : undefined}
            >
              {t(tab.labelKey)}
            </button>
          )
        })}
      </div>
    </nav>
  )
}
