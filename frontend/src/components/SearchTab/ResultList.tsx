import { useState } from 'react';
import type { Leg, RoutePlan, RouteRecommendation, RecommendationSegment, SearchRequest } from '../../types';
import { useLocale } from '../../context/LocaleContext';
import { useFavoritesContext } from '../../context/FavoritesContext';
import { Icon, getEmoji } from '../../icons';
import RouteRecommendationCard from './RouteRecommendationCard';
import './ResultList.css';

interface ResultListProps {
  routes?: RoutePlan[];
  recommendations?: RouteRecommendation[];
  loading: boolean;
  error: string;
  searched: boolean;
  header?: string;
  dataNotice?: string;
  searchId?: string;
  searchRequest?: Partial<SearchRequest>;
  modelVersion?: string;
  datasetVersion?: string;
}

function formatDuration(minutes: number, lang: 'zh' | 'en'): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (lang === 'en') {
    if (h > 0) return `${h}h ${m > 0 ? `${m}m` : ''}`.trim();
    return `${m}m`;
  }
  if (h > 0) return `${h}小时${m > 0 ? `${m}分钟` : ''}`;
  return `${m}分钟`;
}

function formatTime(timeStr: string): string {
  return timeStr.slice(0, 5);
}

function getTransportIcon(type: string): string {
  return type === 'flight' ? getEmoji('transport.flight') : getEmoji('transport.train');
}

function getLevelLabel(t: (key: string) => string, key: string, level: string): string {
  return t(`resultList.${key}.${level}`);
}

function RecommendationCard({
  recommendation,
  index,
  lang,
  t,
}: {
  recommendation: RouteRecommendation;
  index: number;
  lang: 'zh' | 'en';
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const { isFavorite, toggleFavorite } = useFavoritesContext();
  const fav = isFavorite(recommendation.id);
  const path = lang === 'en' && recommendation.city_path_en.length
    ? recommendation.city_path_en
    : recommendation.city_path;

  return (
    <article className="route-card route-card--strategy">
      <div className="route-card__header">
        <div>
          <div className="route-card__strategy-label">{t('resultList.strategyLabel', { index: String(index + 1) })}</div>
          <div className="route-card__path">{path.join(' -> ')}</div>
        </div>
        <button
          className={`route-card__favorite ${fav ? 'active' : ''}`}
          onClick={() => toggleFavorite(recommendation)}
          title={fav ? t('favorites.removeTooltip') : t('favorites.addTooltip')}
          aria-label={fav ? t('favorites.removeTooltip') : t('favorites.addTooltip')}
        >
          <Icon name="actions.heart" size={30} />
        </button>
      </div>

      <div className="route-card__strategy-metrics">
        <span>{t('resultList.estimatedPrice')}: ¥{Math.round(recommendation.estimated_total_price)}</span>
        <span>{t('resultList.estimatedDuration')}: {formatDuration(recommendation.estimated_total_duration_minutes, lang)}</span>
        <span>{recommendation.transfer_count}{t('resultList.transferSuffix')}</span>
        <span>{t('resultList.confidence')}: {Math.round(recommendation.confidence * 100)}%</span>
      </div>

      <div className="route-card__level-row">
        <span>{t('resultList.priceLevel')}: {getLevelLabel(t, 'priceLevels', recommendation.estimated_price_level)}</span>
        <span>{t('resultList.durationLevel')}: {getLevelLabel(t, 'durationLevels', recommendation.estimated_duration_level)}</span>
      </div>

      <div className="route-card__segment-list">
        {recommendation.segments.map((segment, segmentIndex) => (
          <RecommendationSegmentInfo
            key={`${recommendation.id}-${segmentIndex}`}
            segment={segment}
            lang={lang}
            t={t}
          />
        ))}
      </div>

      {recommendation.reasons.length ? (
        <div className="route-card__reason-list">
          {recommendation.reasons.map((reason) => (
            <span key={reason}>{t(`resultList.reasons.${reason}`)}</span>
          ))}
        </div>
      ) : null}

      {recommendation.warnings.length ? (
        <div className="route-card__warning-list">
          {recommendation.warnings.map((warning) => (
            <span key={warning}>{t(`resultList.warnings.${warning}`)}</span>
          ))}
        </div>
      ) : null}

      <div className="route-card__actions">
        <button className="btn btn--primary">{t('resultList.checkSegments')}</button>
      </div>
    </article>
  );
}

function RecommendationSegmentInfo({
  segment,
  lang,
  t,
}: {
  segment: RecommendationSegment;
  lang: 'zh' | 'en';
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const fromCity = lang === 'en' && segment.from_city_en ? segment.from_city_en : segment.from_city;
  const toCity = lang === 'en' && segment.to_city_en ? segment.to_city_en : segment.to_city;
  const availableTypes = segment.available_transport_types
    .map((type) => t(`resultList.transport.${type}`))
    .join(' / ');

  return (
    <div className="route-card__strategy-segment">
      <div className="route-card__leg-route">{fromCity}{' -> '}{toCity}</div>
      <div className="route-card__leg-meta">
        {getTransportIcon(segment.recommended_transport_type)}
        {t('resultList.suggestedTransport')}: {t(`resultList.transport.${segment.recommended_transport_type}`)}
      </div>
      <div className="route-card__segment-meta-grid">
        <span>{t('resultList.availableTransport')}: {availableTypes}</span>
        <span>{t('resultList.estimatedPrice')}: ¥{Math.round(segment.estimated_price)}</span>
        <span>{t('resultList.estimatedDuration')}: {formatDuration(segment.estimated_duration_minutes, lang)}</span>
        <span>{t('resultList.serviceFrequency')}: {getLevelLabel(t, 'frequencyLevels', segment.service_frequency_level)}</span>
      </div>
    </div>
  );
}

function RouteCard({ route, index, lang, t }: { route: RoutePlan; index: number; lang: 'zh' | 'en'; t: (key: string, params?: Record<string, string>) => string }) {
  const [expanded, setExpanded] = useState(false);
  const { isFavorite, toggleFavorite } = useFavoritesContext();
  const fav = isFavorite(route.id);
  const firstLeg = route.legs[0];
  const lastLeg = route.legs[route.legs.length - 1];

  return (
    <div className="route-card">
      <div className="route-card__header">
        <div>
          <div className="route-card__strategy-label">{t('resultList.detailLabel', { index: String(index + 1) })}</div>
          <div className="route-card__price">¥{route.total_price}</div>
        </div>
        <div className="route-card__badge">{formatDuration(route.total_duration_minutes, lang)} · {route.transfer_count}{t('resultList.transferSuffix')}</div>
      </div>
      <div className="route-card__body">
        <div className="route-card__timeline">
          <div className="route-card__time">{formatTime(firstLeg.departure_time)}</div>
          <div className="route-card__line" />
          <div className="route-card__node"><Icon name="status.transferArrow" /></div>
          <div className="route-card__line" />
          <div className="route-card__time">{formatTime(lastLeg.arrival_time)}</div>
        </div>
        <div className="route-card__info">
          {route.legs.map((leg, i) => (
            <LegInfo key={i} leg={leg} index={i} totalLegs={route.legs.length} lang={lang} t={t} />
          ))}
        </div>
        <button
          className={`route-card__favorite ${fav ? 'active' : ''}`}
          onClick={() => toggleFavorite(route)}
          title={fav ? t('favorites.removeTooltip') : t('favorites.addTooltip')}
          aria-label={fav ? t('favorites.removeTooltip') : t('favorites.addTooltip')}
        >
          <Icon name="actions.heart" size={32} />
        </button>
      </div>
      <div className="route-card__actions">
        <button className="btn btn--secondary" onClick={() => setExpanded(!expanded)}>
          {expanded ? t('resultList.collapseDetails') : t('resultList.expandDetails')}
        </button>
        <button className="btn btn--primary">{t('resultList.bookNow')}</button>
      </div>
      {expanded && <TimelineDetail legs={route.legs} lang={lang} t={t} />}
    </div>
  );
}

function LegInfo({ leg, index, totalLegs, lang, t }: { leg: Leg; index: number; totalLegs: number; lang: 'zh' | 'en'; t: (key: string, params?: Record<string, string>) => string }) {
  const fromStation = lang === 'en' && leg.from_station_en ? leg.from_station_en : leg.from_station;
  const toStation = lang === 'en' && leg.to_station_en ? leg.to_station_en : leg.to_station;
  const toCity = lang === 'en' && leg.to_city_en ? leg.to_city_en : leg.to_city;
  const platformLabel = leg.platform ? t(`platform.${leg.platform}`) : '';

  return (
    <>
      <div className="route-card__leg">
        <div className="route-card__leg-route">{fromStation}{' -> '}{toStation}</div>
        <div className="route-card__leg-meta">
          {getTransportIcon(leg.transport_type)} {leg.flight_train_no} · {formatDuration(leg.duration_minutes, lang)}
          {platformLabel && <span className="route-card__platform-tag">{platformLabel}</span>}
        </div>
      </div>
      {index < totalLegs - 1 && (
        <div className="route-card__transfer">
          {getEmoji('status.transferCycle')} {lang === 'en' ? `${t('resultList.transferAt')}${toCity}` : `${toCity}${t('resultList.transferAt')}`}
        </div>
      )}
    </>
  );
}

function TimelineDetail({ legs, lang, t }: { legs: Leg[]; lang: 'zh' | 'en'; t: (key: string, params?: Record<string, string>) => string }) {
  return (
    <div className="timeline-detail">
      {legs.map((leg, i) => {
        const fromStation = lang === 'en' && leg.from_station_en ? leg.from_station_en : leg.from_station;
        const toStation = lang === 'en' && leg.to_station_en ? leg.to_station_en : leg.to_station;
        const fromCity = lang === 'en' && leg.from_city_en ? leg.from_city_en : leg.from_city;
        const toCity = lang === 'en' && leg.to_city_en ? leg.to_city_en : leg.to_city;
        const nextFromStation = lang === 'en' && legs[i + 1]?.from_station_en ? legs[i + 1].from_station_en : legs[i + 1]?.from_station;

        return (
          <div key={i}>
            <div className="timeline-detail__leg">
              <div className="timeline-detail__dot">{getTransportIcon(leg.transport_type)}</div>
              <div className="timeline-detail__datetime">{formatTime(leg.departure_time)} · {leg.departure_date}</div>
              <div className="timeline-detail__station">{fromStation} ({fromCity})</div>
            </div>
            <div className="timeline-detail__segment">
              <div className="timeline-detail__segment-icon">{getTransportIcon(leg.transport_type)}</div>
              <div className="timeline-detail__segment-info">
                <div className="timeline-detail__segment-title">{leg.company} {leg.flight_train_no}{leg.platform && <span className="route-card__platform-tag">{t(`platform.${leg.platform}`)}</span>}</div>
                <div className="timeline-detail__segment-meta">{formatDuration(leg.duration_minutes, lang)} · ¥{leg.price}</div>
              </div>
            </div>
            <div className="timeline-detail__leg">
              <div className="timeline-detail__dot timeline-detail__dot--arrival" />
              <div className="timeline-detail__datetime">{formatTime(leg.arrival_time)} · {leg.arrival_date}</div>
              <div className="timeline-detail__station">{toStation} ({toCity})</div>
            </div>
            {i < legs.length - 1 && (
              <div className="timeline-detail__transfer">
                {getEmoji('status.transferCycle')} {lang === 'en' ? `${t('resultList.transferAt')}${toCity} -> ${nextFromStation}` : `${toCity}${t('resultList.transferAt')} -> ${nextFromStation}`}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function ResultList({
  routes = [],
  recommendations = [],
  loading,
  error,
  searched,
  header,
  dataNotice,
  searchId,
  searchRequest,
  modelVersion,
  datasetVersion,
}: ResultListProps) {
  const { lang, t } = useLocale();
  const hasRecommendations = recommendations.length > 0;
  const hasRoutes = routes.length > 0;
  const totalItems = recommendations.length + routes.length;

  if (loading) {
    return (
      <div className="loading">
        <div className="loading__spinner" />
        <div className="loading__text">{t('resultList.searching')}</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon"><Icon name="status.warning" /></div>
        <div className="empty-state__title">{error}</div>
      </div>
    );
  }

  if (!searched) return null;

  if (!hasRecommendations && !hasRoutes) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon"><Icon name="status.searchEmpty" /></div>
        <div className="empty-state__title">{t('resultList.noRoutesFound')}</div>
        <div className="empty-state__subtitle">{t('resultList.tryAdjust')}</div>
      </div>
    );
  }

  return (
    <div className="results">
      <h2 className="results-header">{header || t('resultList.resultsHeader', { count: String(totalItems) })}</h2>
      {dataNotice && (
        <div className="results-notice">
          {hasRecommendations ? t('resultList.strategyNotice') : t('resultList.mockNotice')}
        </div>
      )}
      <div className="results-list">
        {recommendations.map((recommendation, idx) => (
          <RouteRecommendationCard
            key={recommendation.id}
            recommendation={recommendation}
            index={idx}
            lang={lang}
            t={t}
            searchId={searchId}
            searchRequest={searchRequest}
            modelVersion={modelVersion}
            datasetVersion={datasetVersion}
          />
        ))}
        {routes.map((route, idx) => (
          <RouteCard
            key={route.id}
            route={route}
            index={idx}
            lang={lang}
            t={t}
          />
        ))}
      </div>
    </div>
  );
}
