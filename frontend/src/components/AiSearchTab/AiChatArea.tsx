import { useState, useRef, useEffect } from 'react';
import type { SearchResponse } from '../../types';
import './AiSearchTab.css';

export interface AiChatMessage {
  role: 'user' | 'assistant';
  content: string;
  isSearchResult?: boolean;
  searchData?: SearchResponse;
}

interface AiChatAreaProps {
  messages: AiChatMessage[];
  onSend: (text: string) => void;
  loading: boolean;
  status: string;
  onConfirm: () => void;
  onReject: () => void;
  showConfirm: boolean;
}

export default function AiChatArea({ messages, onSend, loading, status, onConfirm, onReject, showConfirm }: AiChatAreaProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || loading) return;
    onSend(text);
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSend();
  };

  return (
    <div className="ai-search__main">
      <div className="ai-search__messages">
        {messages.length === 0 ? (
          <div className="ai-search__welcome">
            <h2>AI 智能搜索</h2>
            <p>用自然语言描述你的出行需求</p>
            <div className="ai-search__examples">
              <button onClick={() => onSend('北京到上海明天最便宜')}>北京到上海明天最便宜</button>
              <button onClick={() => onSend('帮我找上海到广州的直达高铁')}>帮我找上海到广州的直达高铁</button>
              <button onClick={() => onSend('北京到深圳，预算1000以内，尽量少换乘')}>北京到深圳，预算1000以内，尽量少换乘</button>
              <button onClick={() => onSend('成都到杭州，优先时间短')}>成都到杭州，优先时间短</button>
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <div key={i} className={`ai-search__message ${msg.role === 'user' ? 'ai-search__message--user' : ''}`}>
                <div className="ai-search__message-avatar">{msg.role === 'user' ? '我' : 'AI'}</div>
                <div className="ai-search__message-content">
                  {msg.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="ai-search__message">
                <div className="ai-search__message-avatar">AI</div>
                <div className="ai-search__message-content">思考中...</div>
              </div>
            )}
            {showConfirm && !loading && (
              <div className="ai-search__message">
                <div className="ai-search__message-avatar">AI</div>
                <div className="ai-search__message-content">
                  <div style={{ marginBottom: '12px' }}>已整理好搜索条件，是否确认执行搜索？</div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button className="btn btn--primary" onClick={onConfirm}>确认搜索</button>
                    <button className="btn btn--secondary" onClick={onReject}>再想想</button>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      <div className="ai-search__input-area">
        <div className="ai-search__input-box">
          <input
            type="text"
            placeholder="输入你的出行需求..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <button className="ai-search__send" onClick={handleSend} disabled={loading}>
            ➤
          </button>
        </div>
      </div>
    </div>
  );
}
