import { useState } from 'react';
import type { RoutePlan, Leg } from '../../types';
import { useLocale } from '../../context/LocaleContext';
import { Icon, getEmoji } from '../../icons';
import './ResultList.css';

interface ResultListProps {
  routes: RoutePlan[];
  loading: boolean;
  error: string;
  searched: boolean;
  header?: string;
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

function RouteCard({ route, index, lang, t }: { route: RoutePlan; index: number; lang: 'zh' | 'en'; t: (key: string, params?: Record<string, string>) => string }) {
  const [expanded, setExpanded] = useState(false);
  const firstLeg = route.legs[0];
  const lastLeg = route.legs[route.legs.length - 1];

  return (
    <div className="route-card">
      <div className="route-card__header">
        <div className="route-card__price">¥{route.total_price}</div>
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

  return (
    <>
      <div className="route-card__leg">
        <div className="route-card__leg-route">{fromStation} → {toStation}</div>
        <div className="route-card__leg-meta">
          {getTransportIcon(leg.transport_type)} {leg.flight_train_no} · {formatDuration(leg.duration_minutes, lang)}
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
              <div className="timeline-detail__station">{fromStation}（{fromCity}）</div>
            </div>
            <div className="timeline-detail__segment">
              <div className="timeline-detail__segment-icon">{getTransportIcon(leg.transport_type)}</div>
              <div className="timeline-detail__segment-info">
                <div className="timeline-detail__segment-title">{leg.company} {leg.flight_train_no}</div>
                <div className="timeline-detail__segment-meta">{formatDuration(leg.duration_minutes, lang)} · ¥{leg.price}</div>
              </div>
            </div>
            <div className="timeline-detail__leg">
              <div className="timeline-detail__dot timeline-detail__dot--arrival" />
              <div className="timeline-detail__datetime">{formatTime(leg.arrival_time)} · {leg.arrival_date}</div>
              <div className="timeline-detail__station">{toStation}（{toCity}）</div>
            </div>
            {i < legs.length - 1 && (
              <div className="timeline-detail__transfer">
                {getEmoji('status.transferCycle')} {lang === 'en' ? `${t('resultList.transferAt')}${toCity} → ${nextFromStation}` : `${toCity}${t('resultList.transferAt')} · 换乘至${nextFromStation}`}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function ResultList({ routes, loading, error, searched, header }: ResultListProps) {
  const { lang, t } = useLocale();

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

  if (routes.length === 0) {
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
      <h2 className="results-header">{header || t('resultList.resultsHeader', { count: String(routes.length) })}</h2>
      <div className="results-list">
        {routes.map((route, idx) => (
          <RouteCard key={route.id} route={route} index={idx} lang={lang} t={t} />
        ))}
      </div>
    </div>
  );
}
