import { useState, useRef, useEffect } from 'react';
import type { SearchResponse } from '../../types';
import { useLocale } from '../../context/LocaleContext';
import { Icon } from '../../icons';
import ResultList from '../SearchTab/ResultList';
import './AiSearchTab.css';

export interface AiChatMessage {
  role: 'user' | 'assistant';
  content: string;
  isSearchResult?: boolean;
  searchData?: SearchResponse;
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

const EXAMPLES = [
  { zh: '北京到上海明天最便宜', en: 'Cheapest from Beijing to Shanghai tomorrow' },
  { zh: '帮我找上海到广州的直达高铁', en: 'Direct high-speed train from Shanghai to Guangzhou' },
  { zh: '北京到深圳，预算1000以内，尽量少换乘', en: 'Beijing to Shenzhen under 1000, fewest transfers' },
  { zh: '成都到杭州，优先时间短', en: 'Chengdu to Hangzhou, fastest route' },
];

export default function AiChatArea({ messages, onSend, loading, status, onConfirm, onReject, showConfirm, disabled = false, error = '' }: AiChatAreaProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { lang, t } = useLocale();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || loading || disabled) return;
    onSend(text);
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSend();
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
              {EXAMPLES.map((ex, i) => (
                <button key={i} onClick={() => onSend(lang === 'en' ? ex.en : ex.zh)}>
                  {lang === 'en' ? ex.en : ex.zh}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <div key={i} className={`ai-search__message ${msg.role === 'user' ? 'ai-search__message--user' : ''}`}>
                <div className="ai-search__message-avatar">{msg.role === 'user' ? t('aiChat.userAvatar') : t('aiChat.aiAvatar')}</div>
                <div className={`ai-search__message-content ${msg.searchData ? 'ai-search__message-content--results' : ''}`}>
                  {msg.content}
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
            onChange={(e) => setInput(e.target.value)}
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
