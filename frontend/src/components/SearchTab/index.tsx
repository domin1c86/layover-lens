import { useState, useEffect, useCallback } from 'react';
import type { City, OptimizationTarget, RoutePlan, SearchRequest } from '../../types';
import { cityApi, searchApi } from '../../services/api';
import SearchBar, { type AdvancedFilters } from './SearchBar';
import ResultList from './ResultList';
import './SearchTab.css';

const RECOMMENDATIONS = [
  { from: '北京', to: '上海', label: '航班+火车 · 约4小时' },
  { from: '上海', to: '广州', label: '直达航班 · 约2.5小时' },
  { from: '北京', to: '深圳', label: '多式联运 · 约6小时' },
  { from: '成都', to: '杭州', label: '直达航班 · 约2小时' },
  { from: '西安', to: '南京', label: '高铁直达 · 约5小时' },
  { from: '武汉', to: '重庆', label: '高铁直达 · 约4小时' },
];

export default function SearchTab() {
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

    try {
      const request: SearchRequest = {
        from_city: fromCity,
        to_city: toCity,
        travel_date: date,
        optimization_target: optimize,
      };

      if (advanced.transfer === 'yes') {
        request.max_transfers = 2;
        if (advanced.transferCity) request.required_transfer_cities = [advanced.transferCity];
      } else if (advanced.transfer === 'no') {
        request.max_transfers = 0;
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

  const quickSearch = (from: string, to: string) => {
    const fromCode = cities.find((c) => c.name === from)?.code || from;
    const toCode = cities.find((c) => c.name === to)?.code || to;
    setFromCity(fromCode);
    setToCity(toCode);
  };

  return (
    <div>
      <section className="hero">
        <div className="container">
          <h1 className="hero__title">智能路线规划，让出行更便捷</h1>
          <p className="hero__subtitle">搜索航班与火车的最优中转方案</p>
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
      </section>

      <main className="content">
        <div className="container">
          {!searched && !loading && (
            <div className="empty-state">
              <div className="empty-state__icon">🗺️</div>
              <div className="empty-state__title">输入出发地和目的地，开始搜索最优路线</div>
              <div className="empty-state__subtitle">支持航班、火车及多模式中转组合</div>
            </div>
          )}

          <ResultList routes={routes} loading={loading} error={error} searched={searched} />

          {!searched && !loading && (
            <div className="recommendations">
              <h2 className="recommendations__title">热门路线推荐</h2>
              <div className="city-grid">
                {RECOMMENDATIONS.map((rec) => (
                  <div key={`${rec.from}-${rec.to}`} className="city-grid__item" onClick={() => quickSearch(rec.from, rec.to)}>
                    <div className="city-grid__name">{rec.from} → {rec.to}</div>
                    <div className="city-grid__category">{rec.label}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
