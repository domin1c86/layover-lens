import type { RoutePlan } from '../../types';
import ResultList from './ResultList';
import { useLocale } from '../../context/LocaleContext';
import { Icon } from '../../icons';
import './SearchTab.css';

// Popular city pairs for quick-search suggestions.
// Labels are intentionally generic — real route info comes from the backend search.
const RECOMMENDATIONS = [
  { from: '北京', to: '上海' },
  { from: '上海', to: '广州' },
  { from: '北京', to: '深圳' },
  { from: '成都', to: '杭州' },
  { from: '西安', to: '南京' },
  { from: '武汉', to: '重庆' },
];

interface SearchTabProps {
  routes: RoutePlan[];
  loading: boolean;
  error: string;
  searched: boolean;
  onQuickSearch: (from: string, to: string) => void;
}

export default function SearchTab({ routes, loading, error, searched, onQuickSearch }: SearchTabProps) {
  const { t } = useLocale();
  return (
    <div>
      <section className="hero">
        <div className="container">
          <h1 className="hero__title">{t('searchTab.heroTitle')}</h1>
          <p className="hero__subtitle">{t('searchTab.heroSubtitle')}</p>
        </div>
      </section>

      <main className="content">
        <div className="container">
          {!searched && !loading && (
            <div className="empty-state">
              <div className="empty-state__icon"><Icon name="status.mapEmpty" /></div>
              <div className="empty-state__title">{t('searchTab.emptyTitle')}</div>
              <div className="empty-state__subtitle">{t('searchTab.emptySubtitle')}</div>
            </div>
          )}

          <ResultList routes={routes} loading={loading} error={error} searched={searched} />

          {!searched && !loading && (
            <div className="recommendations">
              <h2 className="recommendations__title">{t('searchTab.recommendations')}</h2>
              <div className="city-grid">
                {RECOMMENDATIONS.map((rec) => (
                  <div key={`${rec.from}-${rec.to}`} className="city-grid__item" onClick={() => onQuickSearch(rec.from, rec.to)}>
                    <div className="city-grid__name">{rec.from} → {rec.to}</div>
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
