import { useState } from 'react';
import type { RoutePlan } from '../../types';
import { RouteTimeline } from '../Timeline';
import './ResultCards.css';

interface RouteCardProps {
  route: RoutePlan;
  index: number;
}

function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours > 0) {
    return `${hours}小时${mins > 0 ? `${mins}分钟` : ''}`;
  }
  return `${mins}分钟`;
}

function formatPrice(price: number): string {
  return `¥${price.toFixed(0)}`;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

export function RouteCard({ route, index }: RouteCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="route-card">
      <div className="route-card__header">
        <div className="route-card__badge">方案 {index + 1}</div>
        <div className="route-card__price">{formatPrice(route.total_price)}</div>
      </div>

      <div className="route-card__summary">
        <div className="route-card__stat">
          <span className="route-card__stat-value">{formatDuration(route.total_duration_minutes)}</span>
          <span className="route-card__stat-label">总时长</span>
        </div>
        <div className="route-card__stat">
          <span className="route-card__stat-value">{route.transfer_count}次</span>
          <span className="route-card__stat-label">换乘</span>
        </div>
        <div className="route-card__stat">
          <span className="route-card__stat-value">{route.legs.length}段</span>
          <span className="route-card__stat-label">行程</span>
        </div>
      </div>

      <div className={`route-card__timeline ${expanded ? 'expanded' : 'collapsed'}`}>
        {expanded ? (
          <RouteTimeline legs={route.legs} />
        ) : (
          <div className="route-card__preview">
            <span className="route-card__preview-icon">🕐</span>
            <span>
              {formatDate(route.legs[0].departure_date)} {route.legs[0].departure_time.slice(0, 5)} 出发 · {' '}
              {formatDate(route.legs[route.legs.length - 1].arrival_date)} {route.legs[route.legs.length - 1].arrival_time.slice(0, 5)} 到达
            </span>
          </div>
        )}
      </div>

      <div className="route-card__actions">
        <button
          className="route-card__btn route-card__btn--secondary"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? '收起详情' : '查看详情'}
        </button>
        <button className="route-card__btn route-card__btn--primary">
          立即预订
        </button>
      </div>
    </div>
  );
}

interface RouteCardListProps {
  routes: RoutePlan[];
}

export function RouteCardList({ routes }: RouteCardListProps) {
  if (routes.length === 0) {
    return (
      <div className="route-list--empty">
        <div className="route-list__empty-icon">🔍</div>
        <p>没有找到符合条件的路线</p>
        <p className="route-list__empty-hint">尝试调整搜索条件或日期</p>
      </div>
    );
  }

  return (
    <div className="route-list">
      <div className="route-list__header">
        <h3>找到 {routes.length} 个方案</h3>
      </div>
      {routes.map((route, index) => (
        <RouteCard key={route.id} route={route} index={index} />
      ))}
    </div>
  );
}
