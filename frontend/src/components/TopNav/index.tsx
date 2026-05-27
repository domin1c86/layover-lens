import { useState, useRef, useEffect } from 'react';
import { motion } from 'motion/react';
import { useTheme } from '../../context/ThemeContext';
import { useLocale } from '../../context/LocaleContext';
import './TopNav.css';

interface TopNavProps {
  activeTab: 'search' | 'ai' | 'favorites';
  onTabChange: (tab: 'search' | 'ai' | 'favorites') => void;
  isCompact?: boolean;
  compactLabel?: string;
  onCompactClick?: () => void;
  onOpenSettings?: () => void;
}

export default function TopNav({ activeTab, onTabChange, isCompact = false, compactLabel = '', onCompactClick, onOpenSettings }: TopNavProps) {
  const { isDark, toggleTheme } = useTheme();
  const { lang, setLang, t } = useLocale();

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
    <nav className={`top-nav ${isCompact ? 'compact' : ''} ${isDark ? 'dark' : ''}`}>
      <div className="container top-nav__inner">
        <a href="#" className="top-nav__logo">
          <div className="top-nav__logo-icon">✈</div>
          <span>中转助手</span>
        </a>

        <div className={`top-nav__tabs ${isCompact ? 'hidden' : ''}`}>
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

        <div className={`tab-indicator ${isCompact ? 'visible' : ''}`}>
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

        <div className={`compact-search ${isCompact ? 'visible' : ''}`} onClick={onCompactClick}>
          <span className="compact-search__label">{compactLabel}</span>
        </div>

        <div className="top-nav__tools">
          <button className="icon-btn" title={t('topNav.theme')} onClick={toggleTheme}>
            {isDark ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="5" />
                <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
              </svg>
            )}
          </button>

          <div className="dropdown" ref={langRef}>
            <button className="icon-btn" title={t('topNav.lang')} onClick={() => toggleDropdown(setLangOpen, setAccountOpen)}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <path d="M2 12h20" />
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
              </svg>
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
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 12h18" />
                <path d="M3 6h18" />
                <path d="M3 18h18" />
              </svg>
              <div style={{ width: '28px', height: '28px', background: 'var(--hairline)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '12px' }}>
                👤
              </div>
            </button>
            <div className={`dropdown-menu ${accountOpen ? 'opening' : 'hidden'}`}>
              <div className="dropdown-surface" />
              <div className="dropdown-content">
                <div className="dropdown-item" onClick={() => { onOpenSettings?.(); setAccountOpen(false); }}>{t('topNav.settings')}</div>
                <div className="dropdown-item">{t('topNav.login')}</div>
                <div className="dropdown-item">{t('topNav.register')}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
