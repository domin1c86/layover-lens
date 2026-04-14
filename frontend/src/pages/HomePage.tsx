import { useState } from 'react';
import type { RoutePlan, OptimizationTarget, SearchRequest } from '../types';
import { searchApi } from '../services/api';
import { SimpleSearchForm } from '../components/SearchForm';
import { RouteCardList } from '../components/ResultCards';
import './HomePage.css';

export default function HomePage() {
  const [routes, setRoutes] = useState<RoutePlan[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searched, setSearched] = useState(false);

  const handleSearch = async (params: {
    from_city: string;
    to_city: string;
    travel_date: string;
    optimization_target: OptimizationTarget;
  }) => {
    setLoading(true);
    setError('');
    setSearched(true);

    try {
      const request: SearchRequest = {
        ...params,
        max_transfers: 3,
      };
      const response = await searchApi.search(request);
      setRoutes(response.routes);
    } catch (err) {
      setError('搜索失败，请稍后重试');
      console.error('Search error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="home-page">
      <header className="home-page__header">
        <div className="home-page__container">
          <h1 className="home-page__title">🌍 中转助手</h1>
          <p className="home-page__subtitle">智能路线规划，让出行更便捷</p>
        </div>
      </header>

      <main className="home-page__main">
        <div className="home-page__container">
          <SimpleSearchForm onSearch={handleSearch} loading={loading} />

          {error && (
            <div className="home-page__error">
              <span className="home-page__error-icon">⚠️</span>
              {error}
            </div>
          )}

          {searched && !loading && (
            <RouteCardList routes={routes} />
          )}

          {!searched && !loading && (
            <div className="home-page__placeholder">
              <div className="home-page__placeholder-icon">🗺️</div>
              <p>输入出发地和目的地，开始搜索最优路线</p>
            </div>
          )}

          {loading && (
            <div className="home-page__loading">
              <div className="home-page__loading-spinner"></div>
              <p>正在搜索最优路线...</p>
            </div>
          )}
        </div>
      </main>

      <footer className="home-page__footer">
        <div className="home-page__container">
          <p>© 2024 中转助手 - Layover Lens</p>
        </div>
      </footer>
    </div>
  );
}
