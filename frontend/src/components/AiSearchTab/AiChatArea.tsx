import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import type { AiToolResult, RouteRecommendation, SearchRequest, SearchResponse, TicketProvider, VerifiedPoi } from '../../types';
import { useLocale } from '../../context/LocaleContext';
import { Icon } from '../../icons';
import RouteFeedbackModal from '../SearchTab/RouteFeedbackModal';
import {
  RoutePath,
  RouteRecommendationDetail,
  formatStrategyDuration,
} from '../SearchTab/RouteRecommendationCard';
import './AiSearchTab.css';

export interface AiChatMessage {
  role: 'user' | 'assistant';
  content: string;
  isSearchResult?: boolean;
  searchData?: SearchResponse;
  finalRequest?: SearchRequest;
  toolResults?: AiToolResult[];
  streaming?: boolean;
}

interface AiChatAreaProps {
  messages: AiChatMessage[];
  onSend: (text: string) => void;
  loading: boolean;
  status: string;
  onConfirm: () => void;
  onReject: () => void;
  showConfirm: boolean;
  disabled?: boolean;
  error?: string;
}

const EXAMPLE_KEYS = [
  'aiChat.exampleCheap',
  'aiChat.exampleDirectTrain',
  'aiChat.exampleBudget',
  'aiChat.exampleFastest',
] as const;

function getVerifiedPois(tool: AiToolResult): VerifiedPoi[] {
  if (tool.name !== 'place_search') return [];
  const pois = tool.data?.verified_pois;
  return Array.isArray(pois) ? pois as VerifiedPoi[] : [];
}

interface ExternalClickState {
  provider: TicketProvider;
  segmentIndex: number;
  recommendation: RouteRecommendation;
  searchData?: SearchResponse;
  finalRequest?: SearchRequest;
}

export default function AiChatArea({
  messages,
  onSend,
  loading,
  status,
  onConfirm,
  onReject,
  showConfirm,
  disabled = false,
  error = '',
}: AiChatAreaProps) {
  const [input, setInput] = useState('');
  const [expandedRoute, setExpandedRoute] = useState<{
    recommendation: RouteRecommendation;
    searchData: SearchResponse;
    finalRequest?: SearchRequest;
  } | null>(null);
  const [lastExternalClick, setLastExternalClick] = useState<ExternalClickState | null>(null);
  const [aiFeedbackOpen, setAiFeedbackOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { lang, t } = useLocale();
  const isSessionBlocked = status === 'blocked';
  const inputDisabled = loading || disabled || isSessionBlocked;
  const hasInput = input.trim().length > 0;
  const sendDisabled = inputDisabled || !hasInput;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || inputDisabled) return;
    onSend(text);
    setInput('');
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') handleSend();
  };

  const latestAiSearch = [...messages].reverse().find((message) => message.searchData?.recommendations?.length);
  const latestRecommendations = latestAiSearch?.searchData?.recommendations || [];

  return (
    <div className="ai-search__main">
      <div className="ai-search__messages">
        {disabled ? (
          <div className="ai-search__welcome ai-search__maintenance">
            <div className="ai-search__maintenance-icon"><Icon name="status.warning" /></div>
            <h2>{t('aiChat.maintenanceTitle')}</h2>
            <p>{t('aiChat.maintenanceSubtitle')}</p>
          </div>
        ) : messages.length === 0 && !isSessionBlocked ? (
          <div className="ai-search__welcome">
            <h2>{t('aiChat.welcomeTitle')}</h2>
            <p>{t('aiChat.welcomeSubtitle')}</p>
            <div className="ai-search__examples">
              {EXAMPLE_KEYS.map((key) => (
                <button key={key} onClick={() => onSend(t(key))}>
                  {t(key)}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`ai-search__message ${msg.role === 'user' ? 'ai-search__message--user' : ''}`}
              >
                <div className="ai-search__message-avatar">
                  {msg.role === 'user' ? t('aiChat.userAvatar') : t('aiChat.aiAvatar')}
                </div>
                <div className={`ai-search__message-content ${msg.searchData ? 'ai-search__message-content--results' : ''}`}>
                  {msg.content ? <div>{msg.content}</div> : null}
                  {msg.toolResults?.length ? (
                    <div className="ai-search__tool-results">
                      {msg.toolResults.map((tool, toolIndex) => (
                        <div
                          key={`${tool.name}-${toolIndex}`}
                          className={`ai-search__tool-result ai-search__tool-result--${tool.status}`}
                        >
                          <span className="ai-search__tool-result-label">
                            {tool.status === 'success' ? t('aiChat.toolResult') : t('aiChat.toolFailed')}
                          </span>
                          <span>{tool.content}</span>
                          {getVerifiedPois(tool).length ? (
                            <div className="ai-search__poi-list">
                              {getVerifiedPois(tool).map((poi) => (
                                <article key={`${poi.provider}-${poi.provider_place_id}`} className="ai-search__poi-card">
                                  <div className="ai-search__poi-card-head">
                                    <strong>{poi.name}</strong>
                                    <span className={`ai-search__poi-badge ai-search__poi-badge--${poi.verification_status}`}>
                                      {poi.verification_status === 'dual_verified'
                                        ? t('aiChat.poiDualVerified')
                                        : t('aiChat.poiSingleVerified')}
                                    </span>
                                  </div>
                                  <div className="ai-search__poi-meta">
                                    {t('aiChat.poiSource')}: {poi.source_providers?.join(' / ') || poi.provider}
                                  </div>
                                  <div className="ai-search__poi-address">{poi.address || t('aiChat.poiAddressUnknown')}</div>
                                  {poi.tags?.length || poi.categories?.length ? (
                                    <div className="ai-search__poi-tags">
                                      {[...(poi.tags || []), ...(poi.categories || [])].slice(0, 5).map((tag) => (
                                        <span key={tag}>{tag}</span>
                                      ))}
                                    </div>
                                  ) : null}
                                </article>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {msg.searchData?.recommendations?.length ? (
                    <AiRouteMiniList
                      recommendations={msg.searchData.recommendations.slice(0, 5)}
                      searchData={msg.searchData}
                      finalRequest={msg.finalRequest}
                      lang={lang}
                      t={t}
                      onOpen={(recommendation) => setExpandedRoute({
                        recommendation,
                        searchData: msg.searchData as SearchResponse,
                        finalRequest: msg.finalRequest,
                      })}
                    />
                  ) : null}
                </div>
              </div>
            ))}
            {loading && (
              <div className="ai-search__message">
                <div className="ai-search__message-avatar">{t('aiChat.aiAvatar')}</div>
                <div className="ai-search__message-content">{t('aiChat.thinking')}</div>
              </div>
            )}
            {showConfirm && !loading && (
              <div className="ai-search__message">
                <div className="ai-search__message-avatar">{t('aiChat.aiAvatar')}</div>
                <div className="ai-search__message-content">
                  <div style={{ marginBottom: '12px' }}>{t('aiChat.confirmPrompt')}</div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button className="btn btn--primary" onClick={onConfirm}>{t('aiChat.confirmSearch')}</button>
                    <button className="btn btn--secondary" onClick={onReject}>{t('aiChat.thinkAgain')}</button>
                  </div>
                </div>
              </div>
            )}
            {error ? <div className="ai-search__stream-error">{error}</div> : null}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      <div className="ai-search__input-area">
        {lastExternalClick ? (
          <button
            type="button"
            className="ai-search__satisfaction-link"
            onClick={() => setAiFeedbackOpen(true)}
          >
            {t('aiChat.satisfactionPrompt')}
          </button>
        ) : null}
        {!disabled && !isSessionBlocked ? (
          <div className="ai-search__scope-hint">{t('aiChat.scopeHint')}</div>
        ) : null}
        {isSessionBlocked ? (
          <div className="ai-search__blocked-note">{t('aiChat.blockedNotice')}</div>
        ) : null}
        <div className="ai-search__input-box">
          <input
            type="text"
            placeholder={isSessionBlocked ? t('aiChat.blockedPlaceholder') : t('aiChat.placeholder')}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={inputDisabled}
          />
          <button className="ai-search__send" onClick={handleSend} disabled={sendDisabled}>
            <Icon name="actions.send" />
          </button>
        </div>
      </div>

      <AnimatePresence>
        {expandedRoute ? (
          <motion.div
            className="ai-route-detail-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setExpandedRoute(null)}
          >
            <motion.article
              layoutId={`ai-route-card-${expandedRoute.recommendation.id}`}
              className="ai-route-detail-card"
              onClick={(event) => event.stopPropagation()}
              initial={{ scale: 0.96 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.96 }}
              transition={{ duration: 0.24, ease: 'easeOut' }}
            >
              <div className="ai-route-detail-card__head">
                <RoutePath recommendation={expandedRoute.recommendation} lang={lang} />
                <button
                  type="button"
                  className="ai-route-detail-card__close"
                  onClick={() => setExpandedRoute(null)}
                  aria-label={t('aiChat.closeRouteDetail')}
                >
                  ×
                </button>
              </div>
              <RouteRecommendationDetail
                recommendation={expandedRoute.recommendation}
                lang={lang}
                t={t}
                searchRequest={expandedRoute.finalRequest}
                onExternalLinkClick={(context) => {
                  setLastExternalClick({
                    ...context,
                    searchData: expandedRoute.searchData,
                    finalRequest: expandedRoute.finalRequest,
                  });
                }}
              />
            </motion.article>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <RouteFeedbackModal
        isOpen={aiFeedbackOpen}
        onClose={() => setAiFeedbackOpen(false)}
        source="ai"
        context="ai_experience"
        searchId={latestAiSearch?.searchData?.search_id}
        searchRequest={latestAiSearch?.finalRequest}
        recommendations={latestRecommendations}
        modelVersion={latestAiSearch?.searchData?.route_model_version}
        datasetVersion={latestAiSearch?.searchData?.route_dataset_version}
        clickedProvider={lastExternalClick?.provider}
        clickedSegmentIndex={lastExternalClick?.segmentIndex}
        t={t}
      />
    </div>
  );
}

function AiRouteMiniList({
  recommendations,
  searchData,
  finalRequest,
  lang,
  t,
  onOpen,
}: {
  recommendations: RouteRecommendation[];
  searchData: SearchResponse;
  finalRequest?: SearchRequest;
  lang: 'zh' | 'en';
  t: (key: string, params?: Record<string, string>) => string;
  onOpen: (recommendation: RouteRecommendation) => void;
}) {
  const dateLabel = finalRequest?.travel_date || searchData.mock_source_date || '';
  return (
    <div className="ai-route-mini-list">
      {recommendations.map((recommendation) => (
        <motion.button
          key={recommendation.id}
          type="button"
          layoutId={`ai-route-card-${recommendation.id}`}
          className="ai-route-mini-card"
          onClick={() => onOpen(recommendation)}
          whileHover={{ y: -2 }}
          transition={{ duration: 0.2 }}
        >
          <span className="ai-route-mini-card__date">{dateLabel}</span>
          <RoutePath recommendation={recommendation} lang={lang} compact />
          <span className="ai-route-mini-card__meta">
            ¥{Math.round(recommendation.estimated_total_price)}
            <span> · </span>
            {formatStrategyDuration(recommendation.estimated_total_duration_minutes, lang)}
          </span>
        </motion.button>
      ))}
      <div className="ai-route-mini-list__notice">{t('aiChat.strategyResultNotice')}</div>
    </div>
  );
}
