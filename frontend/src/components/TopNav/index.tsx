import { useState, useRef, useEffect, useLayoutEffect } from 'react';
import { createPortal } from 'react-dom';
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
  showAiSearch: boolean;
  onOpenSettings?: () => void;
  onOpenLogin?: () => void;
  onOpenRegister?: () => void;
}

export default function TopNav({
  activeTab,
  onTabChange,
  searchDockCompact = false,
  showAiSearch,
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
    ...(showAiSearch ? [{ key: 'ai' as const, label: t('topNav.aiSearch') }] : []),
  ];
  const [langOpen, setLangOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [hoveredIndicator, setHoveredIndicator] = useState<string | null>(null);
  const langButtonRef = useRef<HTMLButtonElement>(null);
  const accountButtonRef = useRef<HTMLButtonElement>(null);
  const langMenuRef = useRef<HTMLDivElement>(null);
  const accountMenuRef = useRef<HTMLDivElement>(null);
  const [langMenuPosition, setLangMenuPosition] = useState({ top: 0, right: 16 });
  const [accountMenuPosition, setAccountMenuPosition] = useState({ top: 0, right: 16 });

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      const target = e.target as Node;
      const isInsideLang =
        langButtonRef.current?.contains(target) || langMenuRef.current?.contains(target);
      const isInsideAccount =
        accountButtonRef.current?.contains(target) || accountMenuRef.current?.contains(target);

      if (!isInsideLang) setLangOpen(false);
      if (!isInsideAccount) setAccountOpen(false);
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setLangOpen(false);
        setAccountOpen(false);
      }
    }

    document.addEventListener('click', handleClick);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('click', handleClick);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  useLayoutEffect(() => {
    if (!langOpen) return;

    const updatePosition = () => {
      const rect = langButtonRef.current?.getBoundingClientRect();
      if (!rect) return;

      setLangMenuPosition({
        top: rect.bottom + 8,
        right: Math.max(12, window.innerWidth - rect.right),
      });
    };

    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);

    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [langOpen]);

  useLayoutEffect(() => {
    if (!accountOpen) return;

    const updatePosition = () => {
      const rect = accountButtonRef.current?.getBoundingClientRect();
      if (!rect) return;

      setAccountMenuPosition({
        top: rect.bottom + 8,
        right: Math.max(12, window.innerWidth - rect.right),
      });
    };

    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);

    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [accountOpen]);

  const toggleDropdown = (
    setter: React.Dispatch<React.SetStateAction<boolean>>,
    otherSetter: React.Dispatch<React.SetStateAction<boolean>>
  ) => {
    otherSetter(false);
    setter((prev) => !prev);
  };

  return (
    <>
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

            <div className="dropdown">
              <button ref={langButtonRef} className="icon-btn" title={t('topNav.lang')} onClick={() => toggleDropdown(setLangOpen, setAccountOpen)}>
                <Icon name="nav.globe" size={16} />
              </button>
            </div>

            <div className="dropdown">
              <button
                ref={accountButtonRef}
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
            </div>
          </div>
        </div>
      </nav>

      {langOpen && typeof document !== 'undefined' && createPortal(
        <div
          ref={langMenuRef}
          className="dropdown-menu top-nav-dropdown-menu opening"
          style={{ top: langMenuPosition.top, right: langMenuPosition.right, minWidth: 120 }}
        >
          <div className="dropdown-surface" />
          <div className="dropdown-content">
            <div className={`dropdown-item ${lang === 'zh' ? 'active' : ''}`} onClick={() => { setLang('zh'); setLangOpen(false); }}>中文</div>
            <div className={`dropdown-item ${lang === 'en' ? 'active' : ''}`} onClick={() => { setLang('en'); setLangOpen(false); }}>English</div>
          </div>
        </div>,
        document.body
      )}

      {accountOpen && typeof document !== 'undefined' && createPortal(
        <div
          ref={accountMenuRef}
          className="dropdown-menu top-nav-dropdown-menu opening"
          style={{ top: accountMenuPosition.top, right: accountMenuPosition.right, minWidth: 160 }}
        >
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
        </div>,
        document.body
      )}
    </>
  );
}
