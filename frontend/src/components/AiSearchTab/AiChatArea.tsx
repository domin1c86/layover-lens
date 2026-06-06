import { useEffect, useRef, useState } from 'react';
import type { AiToolResult, SearchResponse, VerifiedPoi } from '../../types';
import { useLocale } from '../../context/LocaleContext';
import { Icon } from '../../icons';
import ResultList from '../SearchTab/ResultList';
import './AiSearchTab.css';

export interface AiChatMessage {
  role: 'user' | 'assistant';
  content: string;
  isSearchResult?: boolean;
  searchData?: SearchResponse;
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

export default function AiChatArea({
  messages,
  onSend,
  loading,
  onConfirm,
  onReject,
  showConfirm,
  disabled = false,
  error = '',
}: AiChatAreaProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { t } = useLocale();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || loading || disabled) return;
    onSend(text);
    setInput('');
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') handleSend();
  };

  return (
    <div className="ai-search__main">
      <div className="ai-search__messages">
        {disabled ? (
          <div className="ai-search__welcome ai-search__maintenance">
            <div className="ai-search__maintenance-icon"><Icon name="status.warning" /></div>
            <h2>{t('aiChat.maintenanceTitle')}</h2>
            <p>{t('aiChat.maintenanceSubtitle')}</p>
          </div>
        ) : messages.length === 0 ? (
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
                  {msg.searchData ? (
                    <ResultList
                      routes={msg.searchData.routes}
                      loading={false}
                      error=""
                      searched
                      dataNotice={msg.searchData.data_notice}
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
        <div className="ai-search__input-box">
          <input
            type="text"
            placeholder={t('aiChat.placeholder')}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading || disabled}
          />
          <button className="ai-search__send" onClick={handleSend} disabled={loading || disabled}>
            <Icon name="actions.send" />
          </button>
        </div>
      </div>
    </div>
  );
}
