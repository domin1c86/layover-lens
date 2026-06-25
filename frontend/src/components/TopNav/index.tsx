import { useState, useRef, useEffect } from 'react';
import { motion } from 'motion/react';
import { useTheme } from '../../context/ThemeContext';
import { useLocale } from '../../context/LocaleContext';
import { useAuth } from '../../context/AuthContext';
import { Icon } from '../../icons';
import UserAvatar from '../common/UserAvatar';
import './TopNav.css';

interface TopNavProps {
  activeTab: 'search' | 'ai' | 'favorites';
  onTabChange: (tab: 'search' | 'ai' | 'favorites') => void;
  searchDockCompact?: boolean;
  onOpenSettings?: () => void;
  onOpenLogin?: () => void;
  onOpenRegister?: () => void;
}

export default function TopNav({
  activeTab,
  onTabChange,
  searchDockCompact = false,
  onOpenSettings,
  onOpenLogin,
  onOpenRegister,
}: TopNavProps) {
  const { isDark, toggleTheme } = useTheme();
  const { lang, setLang, t } = useLocale();
  const { isLoggedIn, user, logout } = useAuth();

  const TABS = [
    { key: 'search' as const, label: t('topNav.search') },
    { key: 'favorites' as const, label: t('topNav.favorites') },
    { key: 'ai' as const, label: t('topNav.aiSearch') },
  ];
  const [langOpen, setLangOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [hoveredIndicator, setHoveredIndicator] = useState<string | null>(null);
  const langRef = useRef<HTMLDivElement>(null);
  const accountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (!langRef.current?.contains(e.target as Node)) setLangOpen(false);
      if (!accountRef.current?.contains(e.target as Node)) setAccountOpen(false);
    }
    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, []);

  const toggleDropdown = (
    setter: React.Dispatch<React.SetStateAction<boolean>>,
    otherSetter: React.Dispatch<React.SetStateAction<boolean>>
  ) => {
    otherSetter(false);
    setter((prev) => !prev);
  };

  return (
    <nav className={`top-nav ${searchDockCompact ? 'search-dock-compact' : ''} ${isDark ? 'dark' : ''}`}>
      <div className="container top-nav__inner">
        <a href="#" className="top-nav__logo">
          <div className="top-nav__logo-icon"><Icon name="nav.logo" /></div>
          <span>中转助手</span>
        </a>

        <div className={`top-nav__tabs ${searchDockCompact ? 'hidden' : ''}`}>
          {TABS.map((t) => (
            <div
              key={t.key}
              className={`top-nav__tab ${activeTab === t.key ? 'active' : ''}`}
              onClick={() => onTabChange(t.key)}
            >
              {t.label}
            </div>
          ))}
        </div>

        <div className={`tab-indicator ${searchDockCompact ? 'visible' : ''}`}>
          {TABS.map((t) => (
            <motion.div
              key={t.key}
              className="tab-indicator__item"
              onClick={() => {
                if (activeTab !== t.key) {
                  onTabChange(t.key);
                }
              }}
              onHoverStart={() => setHoveredIndicator(t.key)}
              onHoverEnd={() => setHoveredIndicator(null)}
            >
              <div className="tab-indicator__hitbox" />
              <motion.div
                className={`tab-indicator__line-visual ${activeTab === t.key ? 'active' : ''}`}
                animate={{
                  y: hoveredIndicator === t.key && activeTab !== t.key ? -4 : 0,
                }}
                transition={{ type: 'spring', stiffness: 400, damping: 25 }}
              />
            </motion.div>
          ))}
        </div>

        <div className="top-nav__tools">
          <button className="icon-btn" title={t('topNav.theme')} onClick={toggleTheme}>
            <Icon name={isDark ? 'theme.moon' : 'theme.sun'} size={16} />
          </button>

          <div className="dropdown" ref={langRef}>
            <button className="icon-btn" title={t('topNav.lang')} onClick={() => toggleDropdown(setLangOpen, setAccountOpen)}>
              <Icon name="nav.globe" size={16} />
            </button>
            <div className={`dropdown-menu ${langOpen ? 'opening' : 'hidden'}`}>
              <div className="dropdown-surface" />
              <div className="dropdown-content">
                <div className={`dropdown-item ${lang === 'zh' ? 'active' : ''}`} onClick={() => { setLang('zh'); setLangOpen(false); }}>中文</div>
                <div className={`dropdown-item ${lang === 'en' ? 'active' : ''}`} onClick={() => { setLang('en'); setLangOpen(false); }}>English</div>
              </div>
            </div>
          </div>

          <div className="dropdown" ref={accountRef}>
            <button
              className="icon-btn"
              title={t('topNav.account')}
              onClick={() => toggleDropdown(setAccountOpen, setLangOpen)}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '0 8px 0 12px', width: 'auto' }}
            >
              <Icon name="nav.hamburger" size={16} />
              <div
                style={{
                  width: '28px', height: '28px',
                  background: isLoggedIn ? 'var(--primary)' : 'var(--hairline)',
                  color: isLoggedIn ? '#fff' : 'inherit',
                  borderRadius: '50%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '12px', fontWeight: 600,
                }}
              >
                {isLoggedIn ? <UserAvatar user={user} size={28} className="top-nav__avatar" /> : <Icon name="status.userPlaceholder" size={14} />}
              </div>
            </button>
            <div className={`dropdown-menu ${accountOpen ? 'opening' : 'hidden'}`}>
              <div className="dropdown-surface" />
              <div className="dropdown-content">
                <div className="dropdown-item" onClick={() => { onOpenSettings?.(); setAccountOpen(false); }}>{t('topNav.settings')}</div>
                {isLoggedIn ? (
                  <div className="dropdown-item" onClick={() => { logout(); setAccountOpen(false); }}>{t('topNav.logout')}</div>
                ) : (
                  <>
                    <div className="dropdown-item" onClick={() => { onOpenLogin?.(); setAccountOpen(false); }}>{t('topNav.login')}</div>
                    <div className="dropdown-item" onClick={() => { onOpenRegister?.(); setAccountOpen(false); }}>{t('topNav.register')}</div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
