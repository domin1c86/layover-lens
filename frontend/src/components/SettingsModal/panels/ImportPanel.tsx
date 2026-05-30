import { useState } from 'react'
import { useLocale } from '../../../context/LocaleContext'

const OFFICIAL = [
  { key: 'platform12306', name: '铁路 12306' },
]

const THIRD_PARTY = [
  { key: 'platformCtrip', name: '携程旅行' },
  { key: 'platformQunar', name: '去哪儿' },
  { key: 'platformFliggy', name: '飞猪旅行' },
]

export default function ImportPanel() {
  const { t } = useLocale()
  const [enabled, setEnabled] = useState<Record<string, boolean>>({})

  const toggle = (key: string) => {
    setEnabled((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  return (
    <div className="settings-panel">
      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.import.official')}</div>
        <div className="settings-panel__platform-list">
          {OFFICIAL.map((p) => (
            <div key={p.key} className="settings-panel__platform-item">
              <span>{p.name}</span>
              <ToggleSwitch checked={!!enabled[p.key]} onChange={() => toggle(p.key)} />
            </div>
          ))}
        </div>
      </div>

      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.import.thirdParty')}</div>
        <div className="settings-panel__platform-list">
          {THIRD_PARTY.map((p) => (
            <div key={p.key} className="settings-panel__platform-item">
              <span>{p.name}</span>
              <ToggleSwitch checked={!!enabled[p.key]} onChange={() => toggle(p.key)} />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function ToggleSwitch({ checked, onChange }: { checked: boolean; onChange: () => void }) {
  return (
    <button
      className={`settings-panel__toggle ${checked ? 'active' : ''}`}
      onClick={onChange}
      type="button"
      aria-pressed={checked}
    >
      <span className="settings-panel__toggle-knob" />
    </button>
  )
}
