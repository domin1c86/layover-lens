import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { useLocale } from '../../context/LocaleContext'
import { useAuth } from '../../context/AuthContext'
import { Icon } from '../../icons'
import NavMenu, { type SettingsTab } from './NavMenu'
import AccountPanel from './panels/AccountPanel'
import SecurityPanel from './panels/SecurityPanel'
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
  security: SecurityPanel,
  appearance: AppearancePanel,
  aiHistory: AIHistoryPanel,
  import: ImportPanel,
  devices: DevicesPanel,
}

const overlayVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
  exit: { opacity: 0 },
}

const dialogVariants = {
  hidden: { opacity: 0, scale: 0.98, y: -40 },
  visible: { opacity: 1, scale: 1, y: 0 },
  exit: { opacity: 0, scale: 0.98, y: -40 },
}

/** Tabs that require the user to be logged in */
const LOGIN_REQUIRED_TABS: Set<SettingsTab> = new Set(['account', 'security', 'aiHistory', 'devices'])

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { t } = useLocale()
  const { isLoggedIn } = useAuth()
  const [activeTab, setActiveTab] = useState<SettingsTab>('account')
  const contentRef = useRef<HTMLDivElement | null>(null)

  const disabledTabs = useMemo(
    () => (isLoggedIn ? undefined : LOGIN_REQUIRED_TABS),
    [isLoggedIn]
  )

  // Auto-switch to 'appearance' if the active tab becomes disabled
  useEffect(() => {
    if (!isLoggedIn && LOGIN_REQUIRED_TABS.has(activeTab)) {
      setActiveTab('appearance')
    }
  }, [isLoggedIn, activeTab])

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

  useEffect(() => {
    contentRef.current?.scrollTo({ top: 0 })
  }, [activeTab])

  const ActivePanel = PANELS[activeTab]

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          key="settings-overlay"
          className="settings-modal__overlay"
          onClick={onClose}
          role="dialog"
          aria-modal="true"
          aria-label={t('settings.title')}
          variants={overlayVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          transition={{ duration: 0.2 }}
        >
          <motion.div
            key="settings-dialog"
            className="settings-modal__dialog"
            onClick={(e) => e.stopPropagation()}
            variants={dialogVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            transition={{ duration: 0.25, ease: 'easeOut' }}
          >
            <div className="settings-modal__header">
              <h1 className="settings-modal__title">{t('settings.title')}</h1>
              <button className="settings-modal__close" onClick={onClose} aria-label="Close" type="button">
                <Icon name="actions.close" size={16} />
              </button>
            </div>
            <div className="settings-modal__body">
              <NavMenu activeTab={activeTab} onChange={setActiveTab} disabledTabs={disabledTabs} />
              <div className="settings-modal__content" ref={contentRef}>
                <ActivePanel />
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
