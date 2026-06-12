import { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import type {
  ExternalTicketLink,
  RecommendationSegment,
  RouteRecommendation,
  SearchRequest,
  TicketProvider,
} from '../../types';
import { useFavoritesContext } from '../../context/FavoritesContext';
import { Icon, getEmoji } from '../../icons';
import AnimatedModal from '../common/AnimatedModal';
import {
  buildTicketLinks,
  setSkipExternalTicketNotice,
  shouldSkipExternalTicketNotice,
} from '../../services/routeExperience';
import RouteFeedbackModal from './RouteFeedbackModal';
import './ResultList.css';

interface ExternalClickContext {
  provider: TicketProvider;
  segmentIndex: number;
  recommendation: RouteRecommendation;
}

interface RouteRecommendationCardProps {
  recommendation: RouteRecommendation;
  index: number;
  lang: 'zh' | 'en';
  t: (key: string, params?: Record<string, string>) => string;
  searchId?: string;
  searchRequest?: Partial<SearchRequest>;
  modelVersion?: string;
  datasetVersion?: string;
  compact?: boolean;
  onExternalLinkClick?: (context: ExternalClickContext) => void;
}

export function formatStrategyDuration(minutes: number, lang: 'zh' | 'en'): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (lang === 'en') {
    if (h > 0) return `${h}h ${m > 0 ? `${m}m` : ''}`.trim();
    return `${m}m`;
  }
  if (h > 0) return `${h}小时${m > 0 ? `${m}分钟` : ''}`;
  return `${m}分钟`;
}

function getLevelLabel(t: (key: string) => string, key: string, level: string): string {
  return t(`resultList.${key}.${level}`);
}

function getTransportIcon(type: string): string {
  return type === 'flight' ? getEmoji('transport.flight') : getEmoji('transport.train');
}

export function RoutePath({
  recommendation,
  lang,
  compact = false,
}: {
  recommendation: RouteRecommendation;
  lang: 'zh' | 'en';
  compact?: boolean;
}) {
  const cities = lang === 'en' && recommendation.city_path_en.length
    ? recommendation.city_path_en
    : recommendation.city_path;
  return (
    <div className={`route-path-chain ${compact ? 'route-path-chain--compact' : ''}`}>
      {cities.map((city, cityIndex) => (
        <span key={`${city}-${cityIndex}`} className="route-path-chain__item">
          <span className="route-path-chain__city">{city}</span>
          {cityIndex < recommendation.segments.length ? (
            <span className={`route-path-chain__connector route-path-chain__connector--${recommendation.segments[cityIndex].recommended_transport_type}`}>
              <span>{getTransportIcon(recommendation.segments[cityIndex].recommended_transport_type)}</span>
            </span>
          ) : null}
        </span>
      ))}
    </div>
  );
}

export function RouteRecommendationDetail({
  recommendation,
  lang,
  t,
  searchRequest,
  onExternalLinkClick,
}: {
  recommendation: RouteRecommendation;
  lang: 'zh' | 'en';
  t: (key: string, params?: Record<string, string>) => string;
  searchRequest?: Partial<SearchRequest>;
  onExternalLinkClick?: (context: ExternalClickContext) => void;
}) {
  return (
    <div className="route-card__detail-panel">
      <div className="route-card__segment-list">
        {recommendation.segments.map((segment, segmentIndex) => (
          <RecommendationSegmentInfo
            key={`${recommendation.id}-${segmentIndex}`}
            recommendation={recommendation}
            segment={segment}
            segmentIndex={segmentIndex}
            lang={lang}
            t={t}
            searchRequest={searchRequest}
            onExternalLinkClick={onExternalLinkClick}
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
    </div>
  );
}

function RecommendationSegmentInfo({
  recommendation,
  segment,
  segmentIndex,
  lang,
  t,
  searchRequest,
  onExternalLinkClick,
}: {
  recommendation: RouteRecommendation;
  segment: RecommendationSegment;
  segmentIndex: number;
  lang: 'zh' | 'en';
  t: (key: string, params?: Record<string, string>) => string;
  searchRequest?: Partial<SearchRequest>;
  onExternalLinkClick?: (context: ExternalClickContext) => void;
}) {
  const [pendingLink, setPendingLink] = useState<ExternalTicketLink | null>(null);
  const [skipNotice, setSkipNotice] = useState(false);
  const fromCity = lang === 'en' && segment.from_city_en ? segment.from_city_en : segment.from_city;
  const toCity = lang === 'en' && segment.to_city_en ? segment.to_city_en : segment.to_city;
  const availableTypes = segment.available_transport_types
    .map((type) => t(`resultList.transport.${type}`))
    .join(' / ');
  const links = buildTicketLinks(segment, searchRequest);

  const openLink = (link: ExternalTicketLink) => {
    onExternalLinkClick?.({ provider: link.provider, segmentIndex, recommendation });
    window.open(link.url, '_blank', 'noopener,noreferrer');
  };

  const handleLinkClick = (link: ExternalTicketLink) => {
    if (shouldSkipExternalTicketNotice()) {
      openLink(link);
      return;
    }
    setPendingLink(link);
    setSkipNotice(false);
  };

  const confirmOpen = () => {
    if (!pendingLink) return;
    if (skipNotice) setSkipExternalTicketNotice(true);
    openLink(pendingLink);
    setPendingLink(null);
  };

  return (
    <div className="route-card__strategy-segment">
      <div className="route-card__segment-main">
        <div>
          <div className="route-card__leg-route">{fromCity} <span>→</span> {toCity}</div>
          <div className="route-card__leg-meta">
            {getTransportIcon(segment.recommended_transport_type)}
            {t('resultList.suggestedTransport')}: {t(`resultList.transport.${segment.recommended_transport_type}`)}
          </div>
          <div className="route-card__segment-meta-grid">
            <span>{t('resultList.availableTransport')}: {availableTypes}</span>
            <span>{t('resultList.estimatedPrice')}: ¥{Math.round(segment.estimated_price)}</span>
            <span>{t('resultList.estimatedDuration')}: {formatStrategyDuration(segment.estimated_duration_minutes, lang)}</span>
            <span>{t('resultList.serviceFrequency')}: {getLevelLabel(t, 'frequencyLevels', segment.service_frequency_level)}</span>
          </div>
        </div>
        <div className={`route-card__ticket-links route-card__ticket-links--${segment.recommended_transport_type}`}>
          {links.map((link) => (
            <button
              key={link.provider}
              type="button"
              className={`route-card__ticket-link route-card__ticket-link--${link.provider}`}
              onClick={() => handleLinkClick(link)}
            >
              {t(`ticketProviders.${link.provider}`)}
            </button>
          ))}
        </div>
      </div>

      <AnimatedModal
        isOpen={Boolean(pendingLink)}
        overlayClassName="external-link-modal"
        dialogClassName="external-link-modal__dialog"
        ariaLabel={t('externalLink.title')}
        onClose={() => setPendingLink(null)}
      >
        <h2>{t('externalLink.title')}</h2>
        <p>{t('externalLink.description', { provider: pendingLink ? t(`ticketProviders.${pendingLink.provider}`) : '' })}</p>
        <label className="external-link-modal__checkbox">
          <input
            type="checkbox"
            checked={skipNotice}
            onChange={(event) => setSkipNotice(event.target.checked)}
          />
          <span>{t('externalLink.dontRemind')}</span>
        </label>
        <div className="external-link-modal__actions">
          <button type="button" className="btn btn--secondary" onClick={() => setPendingLink(null)}>
            {t('externalLink.cancel')}
          </button>
          <button type="button" className="btn btn--primary external-link-modal__confirm" onClick={confirmOpen}>
            {t('externalLink.continue')}
          </button>
        </div>
      </AnimatedModal>
    </div>
  );
}

export default function RouteRecommendationCard({
  recommendation,
  index,
  lang,
  t,
  searchId,
  searchRequest,
  modelVersion,
  datasetVersion,
  compact = false,
  onExternalLinkClick,
}: RouteRecommendationCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const { isFavorite, toggleFavorite } = useFavoritesContext();
  const fav = isFavorite(recommendation.id);

  if (compact) {
    return (
      <motion.button
        type="button"
        layoutId={`ai-route-card-${recommendation.id}`}
        className="ai-route-mini-card"
        whileHover={{ y: -2 }}
      >
        <RoutePath recommendation={recommendation} lang={lang} compact />
        <span>{t('resultList.estimatedPrice')}: ¥{Math.round(recommendation.estimated_total_price)}</span>
      </motion.button>
    );
  }

  return (
    <article className="route-card route-card--strategy">
      <div className="route-card__header">
        <div>
          <div className="route-card__strategy-label">{t('resultList.strategyLabel', { index: String(index + 1) })}</div>
          <RoutePath recommendation={recommendation} lang={lang} />
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
        <span>{t('resultList.estimatedDuration')}: {formatStrategyDuration(recommendation.estimated_total_duration_minutes, lang)}</span>
        <span>{recommendation.transfer_count}{t('resultList.transferSuffix')}</span>
        <span>{t('resultList.confidence')}: {Math.round(recommendation.confidence * 100)}%</span>
        <span>{t('resultList.priceLevel')}: {getLevelLabel(t, 'priceLevels', recommendation.estimated_price_level)}</span>
        <span>{t('resultList.durationLevel')}: {getLevelLabel(t, 'durationLevels', recommendation.estimated_duration_level)}</span>
      </div>

      <AnimatePresence initial={false}>
        {expanded ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.22 }}
          >
            <RouteRecommendationDetail
              recommendation={recommendation}
              lang={lang}
              t={t}
              searchRequest={searchRequest}
              onExternalLinkClick={onExternalLinkClick}
            />
          </motion.div>
        ) : null}
      </AnimatePresence>

      <div className="route-card__actions">
        <button className="btn btn--secondary" onClick={() => setExpanded((previous) => !previous)}>
          {expanded ? t('resultList.collapseDetails') : t('resultList.expandDetails')}
        </button>
        <button className="btn btn--primary route-card__feedback-btn" onClick={() => setFeedbackOpen(true)}>
          {t('resultList.feedback')}
        </button>
      </div>

      <RouteFeedbackModal
        isOpen={feedbackOpen}
        onClose={() => setFeedbackOpen(false)}
        source="search"
        context="route_card"
        searchId={searchId}
        searchRequest={searchRequest}
        recommendation={recommendation}
        modelVersion={modelVersion}
        datasetVersion={datasetVersion}
        t={t}
      />
    </article>
  );
}
