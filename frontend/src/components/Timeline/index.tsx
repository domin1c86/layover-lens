import type { Leg } from '../../types';
import './Timeline.css';

interface RouteTimelineProps {
  legs: Leg[];
}

function formatTime(timeStr: string): string {
  return timeStr.slice(0, 5); // 只取 HH:MM
}

function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours > 0) {
    return `${hours}小时${mins > 0 ? `${mins}分钟` : ''}`;
  }
  return `${mins}分钟`;
}

function getTransportIcon(type: string): string {
  return type === 'flight' ? '✈️' : '🚄';
}

function getTransportName(type: string): string {
  return type === 'flight' ? '航班' : '火车';
}

export function RouteTimeline({ legs }: RouteTimelineProps) {
  if (legs.length === 0) {
    return null;
  }

  return (
    <div className="route-timeline">
      {legs.map((leg, index) => (
        <div key={index} className="timeline-leg">
          {/* 出发信息 */}
          <div className="timeline-point timeline-point--departure">
            <div className="timeline-point__time">{formatTime(leg.departure_time)}</div>
            <div className="timeline-point__station">{leg.from_station}</div>
            <div className="timeline-point__city">{leg.from_city}</div>
          </div>

          {/* 行程段信息 */}
          <div className="timeline-segment">
            <div className="timeline-segment__line">
              <span className="timeline-segment__icon">{getTransportIcon(leg.transport_type)}</span>
            </div>
            <div className="timeline-segment__info">
              <span className="timeline-segment__transport">
                {getTransportName(leg.transport_type)} {leg.flight_train_no}
              </span>
              <span className="timeline-segment__duration">
                {formatDuration(leg.duration_minutes)}
              </span>
              <span className="timeline-segment__company">{leg.company}</span>
            </div>
          </div>

          {/* 到达信息 */}
          <div className="timeline-point timeline-point--arrival">
            <div className="timeline-point__time">{formatTime(leg.arrival_time)}</div>
            <div className="timeline-point__station">{leg.to_station}</div>
            <div className="timeline-point__city">{leg.to_city}</div>
          </div>

          {/* 中转信息（如果不是最后一段） */}
          {index < legs.length - 1 && (
            <div className="timeline-transfer">
              <div className="timeline-transfer__line"></div>
              <div className="timeline-transfer__info">
                <span className="timeline-transfer__icon">🔄</span>
                <span>中转停留</span>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
