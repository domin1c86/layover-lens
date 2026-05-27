import { useLocale } from '../../context/LocaleContext'

export type SettingsTab = 'account' | 'appearance' | 'aiHistory' | 'import' | 'devices'

interface NavMenuProps {
  activeTab: SettingsTab
  onChange: (tab: SettingsTab) => void
}

const TABS: { key: SettingsTab; labelKey: string }[] = [
  { key: 'account', labelKey: 'settings.menu.account' },
  { key: 'appearance', labelKey: 'settings.menu.appearance' },
  { key: 'aiHistory', labelKey: 'settings.menu.aiHistory' },
  { key: 'import', labelKey: 'settings.menu.import' },
  { key: 'devices', labelKey: 'settings.menu.devices' },
]

export default function NavMenu({ activeTab, onChange }: NavMenuProps) {
  const { t } = useLocale()

  return (
    <nav className="settings-nav" aria-label="Settings navigation">
      <div className="settings-nav__desktop">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`settings-nav__item ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => onChange(tab.key)}
            type="button"
          >
            {t(tab.labelKey)}
          </button>
        ))}
      </div>
      <div className="settings-nav__mobile">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`settings-nav__mobile-item ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => onChange(tab.key)}
            type="button"
          >
            {t(tab.labelKey)}
          </button>
        ))}
      </div>
    </nav>
  )
}
