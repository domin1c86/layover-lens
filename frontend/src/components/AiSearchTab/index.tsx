import { useState, useCallback } from 'react';
import type { SearchRequest, SearchResponse } from '../../types';
import { aiSearchApi } from '../../services/api';
import AiChatArea, { type AiChatMessage } from './AiChatArea';
import './AiSearchTab.css';

type AiStatus = 'idle' | 'collecting' | 'awaiting_confirmation' | 'completed';

interface AiSession {
  sessionId: string | null;
  messages: AiChatMessage[];
  status: AiStatus;
  finalRequest: SearchRequest | null;
  searchResponse: SearchResponse | null;
}

export default function AiSearchTab() {
  const [session, setSession] = useState<AiSession>({
    sessionId: null,
    messages: [],
    status: 'idle',
    finalRequest: null,
    searchResponse: null,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const updateSession = useCallback((partial: Partial<AiSession>) => {
    setSession((prev) => ({ ...prev, ...partial }));
  }, []);

  const handleSend = useCallback(async (text: string) => {
    setError('');
    setLoading(true);

    const userMsg: AiChatMessage = { role: 'user', content: text };
    updateSession({ messages: [...session.messages, userMsg] });

    try {
      let response;
      if (!session.sessionId) {
        response = await aiSearchApi.createSession(text);
      } else {
        response = await aiSearchApi.sendMessage(session.sessionId, text);
      }

      const assistantMsg: AiChatMessage = { role: 'assistant', content: response.assistant_message };
      const newMessages = [...session.messages, userMsg, assistantMsg];

      const newStatus = response.status as AiStatus;
      updateSession({
        sessionId: response.session_id,
        messages: newMessages,
        status: newStatus,
        finalRequest: response.final_request,
        searchResponse: response.search_response,
      });
    } catch (err: any) {
      const status = err?.response?.status;
      const msg = status === 503 ? 'AI 搜索服务暂未配置，请使用普通搜索' : '请求失败，请稍后重试';
      setError(msg);
      updateSession({
        messages: [...session.messages, userMsg, { role: 'assistant', content: msg }],
      });
    } finally {
      setLoading(false);
    }
  }, [session, updateSession]);

  const handleConfirm = useCallback(async () => {
    if (!session.sessionId) return;
    setLoading(true);
    try {
      const response = await aiSearchApi.confirm(session.sessionId, true);
      const assistantMsg: AiChatMessage = {
        role: 'assistant',
        content: response.search_response ? '已为您找到以下路线：' : '搜索完成',
        isSearchResult: true,
        searchData: response.search_response || undefined,
      };
      updateSession({
        messages: [...session.messages, assistantMsg],
        status: response.status as AiStatus,
        searchResponse: response.search_response,
      });
    } catch {
      setError('确认搜索失败');
    } finally {
      setLoading(false);
    }
  }, [session, updateSession]);

  const handleReject = useCallback(async () => {
    if (!session.sessionId) return;
    setLoading(true);
    try {
      const response = await aiSearchApi.confirm(session.sessionId, false);
      const assistantMsg: AiChatMessage = { role: 'assistant', content: response.assistant_message };
      updateSession({
        messages: [...session.messages, assistantMsg],
        status: response.status as AiStatus,
      });
    } catch {
      setError('操作失败');
    } finally {
      setLoading(false);
    }
  }, [session, updateSession]);

  const newChat = () => {
    setSession({
      sessionId: null,
      messages: [],
      status: 'idle',
      finalRequest: null,
      searchResponse: null,
    });
    setError('');
  };

  const historyItems = [
    '北京到上海最便宜',
    '上海到广州高铁',
    '北京到深圳多式联运',
  ];

  return (
    <div className="ai-search">
      <div className="ai-search__sidebar">
        <button className="ai-search__new-chat" onClick={newChat}>+ 新对话</button>
        <div className="ai-search__history">
          {historyItems.map((item, i) => (
            <div key={i} className="ai-search__history-item" onClick={() => handleSend(item)}>
              {item}
            </div>
          ))}
        </div>
      </div>
      <AiChatArea
        messages={session.messages}
        onSend={handleSend}
        loading={loading}
        status={session.status}
        onConfirm={handleConfirm}
        onReject={handleReject}
        showConfirm={session.status === 'awaiting_confirmation'}
      />
    </div>
  );
}
