import { useState, useEffect, useCallback } from 'react'
import { useLocale } from '../../context/LocaleContext'
import NavMenu, { type SettingsTab } from './NavMenu'
import AccountPanel from './panels/AccountPanel'
import AppearancePanel from './panels/AppearancePanel'
import AIHistoryPanel from './panels/AIHistoryPanel'
import ImportPanel from './panels/ImportPanel'
import DevicesPanel from './panels/DevicesPanel'
import './SettingsModal.css'

interface SettingsModalProps {
  isOpen: boolean
  onClose: () => void
}

const PANELS: Record<SettingsTab, React.FC> = {
  account: AccountPanel,
  appearance: AppearancePanel,
  aiHistory: AIHistoryPanel,
  import: ImportPanel,
  devices: DevicesPanel,
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { t } = useLocale()
  const [activeTab, setActiveTab] = useState<SettingsTab>('account')

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    },
    [onClose]
  )

  useEffect(() => {
    if (!isOpen) return
    document.addEventListener('keydown', handleKeyDown)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [isOpen, handleKeyDown])

  if (!isOpen) return null

  const ActivePanel = PANELS[activeTab]

  return (
    <div className="settings-modal__overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label={t('settings.title')}>
      <div className="settings-modal__dialog" onClick={(e) => e.stopPropagation()}>
        <div className="settings-modal__header">
          <h1 className="settings-modal__title">{t('settings.title')}</h1>
          <button className="settings-modal__close" onClick={onClose} aria-label="Close" type="button">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 6L6 18" />
              <path d="M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="settings-modal__body">
          <NavMenu activeTab={activeTab} onChange={setActiveTab} />
          <div className="settings-modal__content">
            <ActivePanel />
          </div>
        </div>
      </div>
    </div>
  )
}
