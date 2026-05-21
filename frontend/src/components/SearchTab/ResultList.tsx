import { useState } from 'react';
import type { RoutePlan, Leg } from '../../types';
import './ResultList.css';

interface ResultListProps {
  routes: RoutePlan[];
  loading: boolean;
  error: string;
  searched: boolean;
  header?: string;
}

function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h > 0) return `${h}小时${m > 0 ? `${m}分钟` : ''}`;
  return `${m}分钟`;
}

function formatTime(timeStr: string): string {
  return timeStr.slice(0, 5);
}

function getTransportIcon(type: string): string {
  return type === 'flight' ? '✈' : '🚄';
}

function RouteCard({ route, index }: { route: RoutePlan; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const firstLeg = route.legs[0];
  const lastLeg = route.legs[route.legs.length - 1];

  return (
    <div className="route-card">
      <div className="route-card__header">
        <div className="route-card__price">¥{route.total_price}</div>
        <div className="route-card__badge">{formatDuration(route.total_duration_minutes)} · {route.transfer_count}次换乘</div>
      </div>
      <div className="route-card__body">
        <div className="route-card__timeline">
          <div className="route-card__time">{formatTime(firstLeg.departure_time)}</div>
          <div className="route-card__line" />
          <div className="route-card__node">⇄</div>
          <div className="route-card__line" />
          <div className="route-card__time">{formatTime(lastLeg.arrival_time)}</div>
        </div>
        <div className="route-card__info">
          {route.legs.map((leg, i) => (
            <LegInfo key={i} leg={leg} index={i} totalLegs={route.legs.length} />
          ))}
        </div>
      </div>
      <div className="route-card__actions">
        <button className="btn btn--secondary" onClick={() => setExpanded(!expanded)}>
          {expanded ? '收起详情' : '展开详情'}
        </button>
        <button className="btn btn--primary">立即预订</button>
      </div>
      {expanded && <TimelineDetail legs={route.legs} />}
    </div>
  );
}

function LegInfo({ leg, index, totalLegs }: { leg: Leg; index: number; totalLegs: number }) {
  return (
    <>
      <div className="route-card__leg">
        <div className="route-card__leg-route">{leg.from_station} → {leg.to_station}</div>
        <div className="route-card__leg-meta">
          {getTransportIcon(leg.transport_type)} {leg.flight_train_no} · {formatDuration(leg.duration_minutes)}
        </div>
      </div>
      {index < totalLegs - 1 && (
        <div className="route-card__transfer">
          🔄 {leg.to_city}中转
        </div>
      )}
    </>
  );
}

function TimelineDetail({ legs }: { legs: Leg[] }) {
  return (
    <div className="timeline-detail">
      {legs.map((leg, i) => (
        <div key={i}>
          <div className="timeline-detail__leg">
            <div className="timeline-detail__dot">{getTransportIcon(leg.transport_type)}</div>
            <div className="timeline-detail__datetime">{formatTime(leg.departure_time)} · {leg.departure_date}</div>
            <div className="timeline-detail__station">{leg.from_station}（{leg.from_city}）</div>
          </div>
          <div className="timeline-detail__segment">
            <div className="timeline-detail__segment-icon">{getTransportIcon(leg.transport_type)}</div>
            <div className="timeline-detail__segment-info">
              <div className="timeline-detail__segment-title">{leg.company} {leg.flight_train_no}</div>
              <div className="timeline-detail__segment-meta">{formatDuration(leg.duration_minutes)} · ¥{leg.price}</div>
            </div>
          </div>
          <div className="timeline-detail__leg">
            <div className="timeline-detail__dot timeline-detail__dot--arrival" />
            <div className="timeline-detail__datetime">{formatTime(leg.arrival_time)} · {leg.arrival_date}</div>
            <div className="timeline-detail__station">{leg.to_station}（{leg.to_city}）</div>
          </div>
          {i < legs.length - 1 && (
            <div className="timeline-detail__transfer">🔄 {leg.to_city}中转 · 换乘至{legs[i + 1].from_station}</div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function ResultList({ routes, loading, error, searched, header }: ResultListProps) {
  if (loading) {
    return (
      <div className="loading">
        <div className="loading__spinner" />
        <div className="loading__text">正在搜索最优路线...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon">⚠️</div>
        <div className="empty-state__title">{error}</div>
      </div>
    );
  }

  if (!searched) return null;

  if (routes.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon">🔍</div>
        <div className="empty-state__title">没有找到符合条件的路线</div>
        <div className="empty-state__subtitle">尝试调整搜索条件或日期</div>
      </div>
    );
  }

  return (
    <div className="results">
      <h2 className="results-header">{header || `找到 ${routes.length} 个方案`}</h2>
      <div className="results-list">
        {routes.map((route, idx) => (
          <RouteCard key={route.id} route={route} index={idx} />
        ))}
      </div>
    </div>
  );
}
