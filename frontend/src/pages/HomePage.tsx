import { useState, useEffect, useCallback, useRef } from 'react';
import type { City, OptimizationTarget, RoutePlan, RouteRecommendation, SearchRequest } from '../types';
import { cityApi, searchApi } from '../services/api';
import { useLocale } from '../context/LocaleContext';
import TopNav from '../components/TopNav';
import SearchTab from '../components/SearchTab';
import AiSearchTab from '../components/AiSearchTab';
import FavoritesTab from '../components/FavoritesTab';
import { type AdvancedFilters } from '../components/SearchTab/SearchBar';
import FloatingSearchDock from '../components/FloatingSearchDock';
import Footer from '../components/Footer';
import MobileBottomNav from '../components/MobileBottomNav';
import './HomePage.css';

interface HomePageProps {
  onOpenSettings?: () => void
  onOpenLogin?: () => void
  onOpenRegister?: () => void
}

export default function HomePage({ onOpenSettings, onOpenLogin, onOpenRegister }: HomePageProps) {
  const { t } = useLocale();
  const [activeTab, setActiveTab] = useState<'search' | 'ai' | 'favorites'>('search');
  const [searchDockCompact, setSearchDockCompact] = useState(false);
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

  useEffect(() => {
    if (activeTab !== 'ai') {
      setAiFooterOpen(false);
    }
    if (activeTab !== 'search') {
      setSearchDockCompact(false);
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

  const searchDockBehavior: 'scroll' | 'temporary' = activeTab === 'ai' ? 'temporary' : 'scroll';
  const topNavSearchCompact = activeTab === 'ai' || searchDockCompact;

  return (
    <div className="home-page">
      <div className="home-page__main">
        <TopNav
          activeTab={activeTab}
          onTabChange={setActiveTab}
          searchDockCompact={topNavSearchCompact}
          onOpenSettings={onOpenSettings}
          onOpenLogin={onOpenLogin}
          onOpenRegister={onOpenRegister}
        />

        <div className={`home-page__search-placeholder home-page__search-placeholder--${activeTab}`} />
        <FloatingSearchDock
          behavior={searchDockBehavior}
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
          onCompactChange={setSearchDockCompact}
        />

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

      <MobileBottomNav activeTab={activeTab} onTabChange={setActiveTab} />

      {(activeTab !== 'ai' || aiFooterOpen) && (
        <div ref={footerRef}>
          <Footer />
        </div>
      )}
    </div>
  );
}
