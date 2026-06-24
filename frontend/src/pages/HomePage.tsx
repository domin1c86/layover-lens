import { useState, useEffect, useCallback, useRef } from 'react';
import { AnimatePresence, LayoutGroup, motion } from 'motion/react';
import type { City, OptimizationTarget, RoutePlan, RouteRecommendation, SearchRequest } from '../types';
import { cityApi, searchApi } from '../services/api';
import { useTheme } from '../context/ThemeContext';
import { useLocale } from '../context/LocaleContext';
import TopNav from '../components/TopNav';
import SearchTab from '../components/SearchTab';
import AiSearchTab from '../components/AiSearchTab';
import FavoritesTab from '../components/FavoritesTab';
import SearchBar, { type AdvancedFilters } from '../components/SearchTab/SearchBar';
import Footer from '../components/Footer';
import MobileBottomNav from '../components/MobileBottomNav';
import './HomePage.css';

const COMPACT_SCROLL_Y = 160;
const EXPAND_SCROLL_Y = 12;
const RECOMPACT_SCROLL_DELTA = 24;
const COMPACT_TRANSITION_MS = 550;

interface HomePageProps {
  onOpenSettings?: () => void
  onOpenLogin?: () => void
  onOpenRegister?: () => void
}

export default function HomePage({ onOpenSettings, onOpenLogin, onOpenRegister }: HomePageProps) {
  const { isDark } = useTheme();
  const { lang, t } = useLocale();
  const [activeTab, setActiveTab] = useState<'search' | 'ai' | 'favorites'>('search');
  const [isCompact, setIsCompact] = useState(false);
  const [isMorphingSearch, setIsMorphingSearch] = useState(false);
  const [isMobileViewport, setIsMobileViewport] = useState(() => window.matchMedia('(max-width: 744px)').matches);
  const [aiFooterOpen, setAiFooterOpen] = useState(false);
  const footerRef = useRef<HTMLDivElement>(null);

  const [cities, setCities] = useState<City[]>([]);
  const [fromCity, setFromCity] = useState('');
  const [toCity, setToCity] = useState('');
  const [date, setDate] = useState(() => {
    const today = new Date();
    return today.toISOString().split('T')[0];
  });
  const [optimize, setOptimize] = useState<OptimizationTarget>('balanced');
  const [routes, setRoutes] = useState<RoutePlan[]>([]);
  const [recommendations, setRecommendations] = useState<RouteRecommendation[]>([]);
  const [searchId, setSearchId] = useState('');
  const [lastSearchRequest, setLastSearchRequest] = useState<Partial<SearchRequest>>({});
  const [routeModelVersion, setRouteModelVersion] = useState('');
  const [routeDatasetVersion, setRouteDatasetVersion] = useState('');
  const [dataNotice, setDataNotice] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searched, setSearched] = useState(false);

  const isTransitioning = useRef(false);
  const lastScrollY = useRef(window.scrollY);
  const activeTabRef = useRef(activeTab);
  const prevActiveTabRef = useRef(activeTab);
  const expandedAtRef = useRef(window.scrollY);
  const transitionTimeoutRef = useRef<number | undefined>();

  const startCompactTransition = useCallback((nextIsCompact: boolean) => {
    isTransitioning.current = true;
    setIsMorphingSearch(true);
    if (transitionTimeoutRef.current !== undefined) {
      window.clearTimeout(transitionTimeoutRef.current);
    }

    transitionTimeoutRef.current = window.setTimeout(() => {
      isTransitioning.current = false;
      const currentY = window.scrollY;
      lastScrollY.current = currentY;

      if (!nextIsCompact) {
        expandedAtRef.current = currentY;
      }

      transitionTimeoutRef.current = undefined;
      setIsMorphingSearch(false);
    }, COMPACT_TRANSITION_MS);
  }, []);

  useEffect(() => {
    activeTabRef.current = activeTab;
  }, [activeTab]);

  useEffect(() => {
    const media = window.matchMedia('(max-width: 744px)');
    const handleViewportChange = () => setIsMobileViewport(media.matches);
    handleViewportChange();
    media.addEventListener('change', handleViewportChange);
    return () => media.removeEventListener('change', handleViewportChange);
  }, []);

  useEffect(() => {
    const handleScroll = () => {
      if (isTransitioning.current) return;

      const y = window.scrollY;
      lastScrollY.current = y;

      setIsCompact((prev) => {
        // AI 搜索标签页强制保持 compact
        if (activeTabRef.current === 'ai') {
          if (!prev) {
            startCompactTransition(true);
          }
          return true;
        }

        let next = prev;
        const compactThreshold = Math.max(COMPACT_SCROLL_Y, expandedAtRef.current + RECOMPACT_SCROLL_DELTA);

        // 收起：必须滚过一个稳定阈值，避免搜索栏高度变化造成 scrollY 回弹后反复触发
        if (!prev && y >= compactThreshold) {
          next = true;
        }
        // 展开：只在回到页面顶部附近时自动展开；中间区域通过顶栏 compact search 手动展开
        else if (prev && y <= EXPAND_SCROLL_Y) {
          next = false;
        }

        if (next !== prev) {
          startCompactTransition(next);
        }
        return next;
      });
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => {
      window.removeEventListener('scroll', handleScroll);
      if (transitionTimeoutRef.current !== undefined) {
        window.clearTimeout(transitionTimeoutRef.current);
      }
      setIsMorphingSearch(false);
    };
  }, [startCompactTransition]);

  useEffect(() => {
    if (prevActiveTabRef.current === activeTab) return;
    prevActiveTabRef.current = activeTab;

    if (activeTab === 'ai') {
      setIsCompact(true);
      startCompactTransition(true);
    } else {
      setIsCompact(false);
      startCompactTransition(false);
    }
  }, [activeTab, startCompactTransition]);

  useEffect(() => {
    if (activeTab !== 'ai') {
      setAiFooterOpen(false);
    }
  }, [activeTab]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (!aiFooterOpen) return;
      const target = e.target as Node;
      if (footerRef.current?.contains(target)) return;
      const aboutBtn = document.querySelector('[data-about-btn]');
      if (aboutBtn?.contains(target)) return;
      setAiFooterOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [aiFooterOpen]);

  useEffect(() => {
    cityApi.getCities().then((data) => {
      setCities(data);
      if (data.length > 0) setFromCity(data[0].code);
      if (data.length > 1) setToCity(data[1].code);
    }).catch(() => setError(t('errors.loadCitiesFailed')));
  }, []);

  const handleSearch = useCallback(async (advanced: AdvancedFilters) => {
    if (!fromCity || !toCity || !date) {
      setError(t('errors.incompleteSearch'));
      return;
    }
    if (fromCity === toCity) {
      setError(t('errors.sameCity'));
      return;
    }
    setError('');
    setLoading(true);
    setSearched(true);
    setActiveTab('search');

    try {
      const request: SearchRequest = {
        from_city: fromCity,
        to_city: toCity,
        travel_date: date,
        optimization_target: optimize,
      };

      if (advanced.transfer === 'no') {
        request.max_transfers = 0;
      } else {
        if (advanced.transferCountMin) {
          request.min_transfers = Number(advanced.transferCountMin);
        }
        if (advanced.transferCountMax) {
          request.max_transfers = Number(advanced.transferCountMax);
        } else if (advanced.transfer === 'yes') {
          request.max_transfers = 2;
        }
      }

      if (advanced.transferCities.length > 0) {
        request.required_transfer_cities = advanced.transferCities;
      }

      if (advanced.priceMax) {
        request.max_price = Number(advanced.priceMax);
      }

      if (advanced.transportTypes.length > 0 && advanced.transportTypes.length < 2) {
        request.preferred_transport_types = advanced.transportTypes;
      }

      const response = await searchApi.search(request);
      setRoutes(response.routes || []);
      setRecommendations(response.recommendations || []);
      setSearchId(response.search_id || '');
      setLastSearchRequest(request);
      setRouteModelVersion(response.route_model_version || '');
      setRouteDatasetVersion(response.route_dataset_version || '');
      setDataNotice(response.strategy_notice || response.data_notice || '');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || t('errors.searchFailed');
      setError(msg);
      setDataNotice('');
      setRecommendations([]);
      setSearchId('');
    } finally {
      setLoading(false);
    }
  }, [fromCity, toCity, date, optimize]);

  const handleQuickSearch = useCallback((from: string, to: string) => {
    const fromCode = cities.find((c) => c.name === from)?.code || from;
    const toCode = cities.find((c) => c.name === to)?.code || to;
    setFromCity(fromCode);
    setToCity(toCode);
  }, [cities]);

  const handleCompactClick = useCallback(() => {
    if (activeTab === 'ai') return;
    setIsCompact(false);
    startCompactTransition(false);
  }, [activeTab, startCompactTransition]);

  const fromCityName = cities.find((c) => c.code === fromCity)?.name || fromCity;
  const toCityName = cities.find((c) => c.code === toCity)?.name || toCity;
  const formatDateLabel = (iso: string) => {
    if (!iso) return '';
    const d = new Date(iso + 'T00:00:00');
    if (lang === 'en') {
      return `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
    }
    return `${d.getMonth() + 1}月${d.getDate()}日`;
  };
  const compactLabel = `${fromCityName} → ${toCityName} · ${formatDateLabel(date)}`;
  const effectiveCompact = isCompact && !isMobileViewport;

  return (
    <div className={`home-page ${isMorphingSearch ? 'search-morphing' : ''}`}>
      <LayoutGroup id="travel-search-morph">
      <div className="home-page__main">
        <TopNav
          activeTab={activeTab}
          onTabChange={setActiveTab}
          isCompact={effectiveCompact}
          compactLabel={compactLabel}
          onCompactClick={handleCompactClick}
          onOpenSettings={onOpenSettings}
          onOpenLogin={onOpenLogin}
          onOpenRegister={onOpenRegister}
        />

        <div className={`home-page__search-bar ${effectiveCompact ? 'compact' : ''} ${isDark ? 'dark' : ''}`}>
          <div className="container">
            <AnimatePresence initial={false}>
              {!effectiveCompact ? (
                <motion.div
                  key="expanded-search"
                  className="home-page__search-motion"
                  initial={false}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 1 }}
                  transition={{ duration: 0 }}
                >
                  <SearchBar
                    cities={cities}
                    fromCity={fromCity}
                    toCity={toCity}
                    date={date}
                    optimize={optimize}
                    onFromChange={setFromCity}
                    onToChange={setToCity}
                    onDateChange={setDate}
                    onOptimizeChange={setOptimize}
                    onSearch={handleSearch}
                    loading={loading}
                    morphLayoutId="travel-search-shell"
                  />
                </motion.div>
              ) : null}
            </AnimatePresence>
          </div>
        </div>

        <div className="home-page__content">
          {activeTab === 'search' && (
            <SearchTab
              routes={routes}
              recommendations={recommendations}
              loading={loading}
              error={error}
              searched={searched}
              dataNotice={dataNotice}
              searchId={searchId}
              searchRequest={lastSearchRequest}
              modelVersion={routeModelVersion}
              datasetVersion={routeDatasetVersion}
              onQuickSearch={handleQuickSearch}
            />
          )}
          {activeTab === 'ai' && (
            <div className="home-page__tab-panel">
              <AiSearchTab aboutOpen={aiFooterOpen} onToggleAbout={() => setAiFooterOpen((prev) => !prev)} />
            </div>
          )}
          {activeTab === 'favorites' && <FavoritesTab />}
        </div>
      </div>
      </LayoutGroup>

      <MobileBottomNav activeTab={activeTab} onTabChange={setActiveTab} />

      {(activeTab !== 'ai' || aiFooterOpen) && (
        <div ref={footerRef}>
          <Footer />
        </div>
      )}
    </div>
  );
}
