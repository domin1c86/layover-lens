import { useState, useEffect, useCallback, useRef } from 'react';
import type { City, OptimizationTarget, RoutePlan, SearchRequest } from '../types';
import { cityApi, searchApi } from '../services/api';
import TopNav from '../components/TopNav';
import SearchTab from '../components/SearchTab';
import AiSearchTab from '../components/AiSearchTab';
import FavoritesTab from '../components/FavoritesTab';
import SearchBar, { type AdvancedFilters } from '../components/SearchTab/SearchBar';
import Footer from '../components/Footer';
import './HomePage.css';

const COMPACT_DOWN_THRESHOLD = 60; // 向下滚动超过此值 → 缩短
const COMPACT_UP_THRESHOLD = 30;    // 向上滚动低于此值 → 展开

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<'search' | 'ai' | 'favorites'>('search');
  const [isCompact, setIsCompact] = useState(false);
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searched, setSearched] = useState(false);

  const isTransitioning = useRef(false);
  const lastScrollY = useRef(window.scrollY);
  const activeTabRef = useRef(activeTab);

  useEffect(() => {
    activeTabRef.current = activeTab;
  }, [activeTab]);

  useEffect(() => {
    const handleScroll = () => {
      if (isTransitioning.current) return;

      const y = window.scrollY;
      const delta = y - lastScrollY.current;
      lastScrollY.current = y;

      setIsCompact((prev) => {
        // AI 搜索标签页强制保持 compact
        if (activeTabRef.current === 'ai') {
          if (!prev) {
            isTransitioning.current = true;
            setTimeout(() => {
              isTransitioning.current = false;
              lastScrollY.current = window.scrollY;
            }, 350);
          }
          return true;
        }

        const topBarHeight = prev ? 80 : 164;
        const effectiveY = Math.max(0, y - topBarHeight);

        let next = prev;
        // 只有向下滚动才能触发 compact
        if (!prev && delta > 0 && effectiveY > COMPACT_DOWN_THRESHOLD) {
          next = true;
        }
        // 只有向上滚动才能触发 expand
        else if (prev && delta < 0 && effectiveY < COMPACT_UP_THRESHOLD) {
          next = false;
        }

        if (next !== prev) {
          isTransitioning.current = true;
          setTimeout(() => {
            isTransitioning.current = false;
            lastScrollY.current = window.scrollY;
          }, 350);
        }
        return next;
      });
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    if (activeTab === 'ai' && !isCompact) {
      setIsCompact(true);
      isTransitioning.current = true;
      setTimeout(() => {
        isTransitioning.current = false;
        lastScrollY.current = window.scrollY;
      }, 350);
    }
  }, [activeTab, isCompact]);

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
    }).catch(() => setError('加载城市列表失败'));
  }, []);

  const handleSearch = useCallback(async (advanced: AdvancedFilters) => {
    if (!fromCity || !toCity || !date) {
      setError('请填写完整的搜索信息');
      return;
    }
    if (fromCity === toCity) {
      setError('出发城市和目的城市不能相同');
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
      setRoutes(response.routes);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || '搜索失败，请稍后重试';
      setError(msg);
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
    isTransitioning.current = true;
    setTimeout(() => {
      isTransitioning.current = false;
      lastScrollY.current = window.scrollY;
    }, 350);
  }, [activeTab]);

  const fromCityName = cities.find((c) => c.code === fromCity)?.name || fromCity;
  const toCityName = cities.find((c) => c.code === toCity)?.name || toCity;
  const formatDateLabel = (iso: string) => {
    if (!iso) return '';
    const d = new Date(iso + 'T00:00:00');
    return `${d.getMonth() + 1}月${d.getDate()}日`;
  };
  const compactLabel = `${fromCityName} → ${toCityName} · ${formatDateLabel(date)}`;

  return (
    <div className="home-page">
      <div className="home-page__main">
        <TopNav
          activeTab={activeTab}
          onTabChange={setActiveTab}
          isCompact={isCompact}
          compactLabel={compactLabel}
          onCompactClick={handleCompactClick}
        />

        <div className={`home-page__search-bar ${isCompact ? 'compact' : ''}`}>
          <div className="container">
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
            />
          </div>
        </div>

        <div className="home-page__content">
          {activeTab === 'search' && (
            <SearchTab
              routes={routes}
              loading={loading}
              error={error}
              searched={searched}
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

      {(activeTab !== 'ai' || aiFooterOpen) && (
        <div ref={footerRef}>
          <Footer />
        </div>
      )}
    </div>
  );
}
