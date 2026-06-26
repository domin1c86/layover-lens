import { Icon } from '../../icons';
import { useLocale } from '../../context/LocaleContext';
import './MobileBottomNav.css';

type TabKey = 'search' | 'ai' | 'favorites';

interface MobileBottomNavProps {
  activeTab: TabKey;
  onTabChange: (tab: TabKey) => void;
  showAiSearch: boolean;
}

export default function MobileBottomNav({ activeTab, onTabChange, showAiSearch }: MobileBottomNavProps) {
  const { t } = useLocale();
  const tabs = [
    { key: 'search' as const, label: t('topNav.search'), icon: <Icon name="actions.search" size={18} /> },
    ...(showAiSearch ? [{ key: 'ai' as const, label: t('topNav.aiSearch'), icon: <span aria-hidden="true">AI</span> }] : []),
    { key: 'favorites' as const, label: t('topNav.favorites'), icon: <Icon name="actions.heart" size={18} /> },
  ];

  return (
    <nav className="mobile-bottom-nav" aria-label="Mobile navigation">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          className={`mobile-bottom-nav__item ${activeTab === tab.key ? 'active' : ''}`}
          onClick={() => onTabChange(tab.key)}
          aria-current={activeTab === tab.key ? 'page' : undefined}
        >
          <span className="mobile-bottom-nav__icon">{tab.icon}</span>
          <span className="mobile-bottom-nav__label">{tab.label}</span>
        </button>
      ))}
    </nav>
  );
}
