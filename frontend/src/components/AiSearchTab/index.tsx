import { useState, useCallback, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import type { SearchRequest, SearchResponse } from '../../types';
import { aiSearchApi } from '../../services/api';
import AiChatArea, { type AiChatMessage } from './AiChatArea';
import './AiSearchTab.css';

type AiStatus = 'idle' | 'collecting' | 'awaiting_confirmation' | 'completed';

interface Session {
  id: string;
  sessionId: string | null;
  messages: AiChatMessage[];
  status: AiStatus;
  finalRequest: SearchRequest | null;
  searchResponse: SearchResponse | null;
  title: string;
}

interface AiSearchTabProps {
  aboutOpen?: boolean;
  onToggleAbout?: () => void;
}

let nextSessionId = 1;

function createEmptySession(): Session {
  return {
    id: `local-${nextSessionId++}`,
    sessionId: null,
    messages: [],
    status: 'idle',
    finalRequest: null,
    searchResponse: null,
    title: '新对话',
  };
}

export default function AiSearchTab({ aboutOpen, onToggleAbout }: AiSearchTabProps) {
  const [sessions, setSessions] = useState<Session[]>(() => [createEmptySession()]);
  const [activeSessionId, setActiveSessionId] = useState<string>(sessions[0].id);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const editInputRef = useRef<HTMLInputElement>(null);
  const editTitleRef = useRef(editTitle);
  editTitleRef.current = editTitle;

  const startEdit = (session: Session) => {
    if (confirmingDeleteId) {
      cancelDelete();
    }
    setEditingSessionId(session.id);
    setEditTitle(session.title);
  };

  const saveEdit = () => {
    if (editingSessionId) {
      const trimmed = editTitle.trim();
      setSessions((prev) =>
        prev.map((s) => (s.id === editingSessionId ? { ...s, title: trimmed || s.title } : s))
      );
      setEditingSessionId(null);
    }
  };

  const cancelEdit = () => {
    setEditingSessionId(null);
    setEditTitle('');
  };

  const cancelDelete = () => {
    setConfirmingDeleteId(null);
  };

  const handleFirstDeleteClick = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (editingSessionId) {
      cancelEdit();
    }
    setConfirmingDeleteId(sessionId);
  };

  const handleTrashClick = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    setDeletingId(sessionId);
    setConfirmingDeleteId(null);
    setTimeout(() => {
      deleteSession(sessionId);
      setDeletingId((prev) => (prev === sessionId ? null : prev));
    }, 600);
  };

  useEffect(() => {
    if (!confirmingDeleteId) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        cancelDelete();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [confirmingDeleteId]);

  useEffect(() => {
    if (editingSessionId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingSessionId]);

  useEffect(() => {
    if (!editingSessionId && !confirmingDeleteId) return;
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Element;
      if (editingSessionId && !target.closest('.ai-search__history-item')) {
        const trimmed = editTitleRef.current.trim();
        setSessions((prev) =>
          prev.map((s) => (s.id === editingSessionId ? { ...s, title: trimmed || s.title } : s))
        );
        setEditingSessionId(null);
      }
      if (confirmingDeleteId && !target.closest('.ai-search__history-row')) {
        cancelDelete();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [editingSessionId, confirmingDeleteId]);

  const activeSession = sessions.find((s) => s.id === activeSessionId) || sessions[0];

  const updateActiveSession = useCallback((partial: Partial<Session>) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === activeSessionId ? { ...s, ...partial } : s))
    );
  }, [activeSessionId]);

  const handleSend = useCallback(async (text: string) => {
    setError('');
    setLoading(true);

    const userMsg: AiChatMessage = { role: 'user', content: text };
    const currentMessages = [...activeSession.messages, userMsg];

    const newTitle =
      activeSession.messages.length === 0 && activeSession.title === '新对话'
        ? text.slice(0, 10) + (text.length > 10 ? '...' : '')
        : activeSession.title;

    updateActiveSession({ messages: currentMessages, title: newTitle });

    try {
      let response;
      if (!activeSession.sessionId) {
        response = await aiSearchApi.createSession(text);
      } else {
        response = await aiSearchApi.sendMessage(activeSession.sessionId, text);
      }

      const assistantMsg: AiChatMessage = { role: 'assistant', content: response.assistant_message };
      const newMessages = [...currentMessages, assistantMsg];

      const newStatus = response.status as AiStatus;
      updateActiveSession({
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
      updateActiveSession({
        messages: [...currentMessages, { role: 'assistant', content: msg }],
      });
    } finally {
      setLoading(false);
    }
  }, [activeSession, updateActiveSession]);

  const handleConfirm = useCallback(async () => {
    if (!activeSession.sessionId) return;
    setLoading(true);
    try {
      const response = await aiSearchApi.confirm(activeSession.sessionId, true);
      const assistantMsg: AiChatMessage = {
        role: 'assistant',
        content: response.search_response ? '已为您找到以下路线：' : '搜索完成',
        isSearchResult: true,
        searchData: response.search_response || undefined,
      };
      updateActiveSession({
        messages: [...activeSession.messages, assistantMsg],
        status: response.status as AiStatus,
        searchResponse: response.search_response,
      });
    } catch {
      setError('确认搜索失败');
    } finally {
      setLoading(false);
    }
  }, [activeSession, updateActiveSession]);

  const handleReject = useCallback(async () => {
    if (!activeSession.sessionId) return;
    setLoading(true);
    try {
      const response = await aiSearchApi.confirm(activeSession.sessionId, false);
      const assistantMsg: AiChatMessage = { role: 'assistant', content: response.assistant_message };
      updateActiveSession({
        messages: [...activeSession.messages, assistantMsg],
        status: response.status as AiStatus,
      });
    } catch {
      setError('操作失败');
    } finally {
      setLoading(false);
    }
  }, [activeSession, updateActiveSession]);

  const newChat = () => {
    const emptySession = sessions.find((s) => s.messages.length === 0);
    if (emptySession) {
      setActiveSessionId(emptySession.id);
      setError('');
      return;
    }

    const newSession = createEmptySession();
    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
    setError('');
  };

  const deleteSession = (sessionId: string) => {
    const filtered = sessions.filter((s) => s.id !== sessionId);
    if (filtered.length === 0) {
      const newSession = createEmptySession();
      setSessions([newSession]);
      setActiveSessionId(newSession.id);
    } else {
      setSessions(filtered);
      if (activeSessionId === sessionId) {
        setActiveSessionId(filtered[0].id);
      }
    }
    setError('');
  };

  return (
    <div className="ai-search">
      <div className="ai-search__sidebar">
        <button className="ai-search__new-chat" onClick={newChat}>
          <span className="ai-search__new-chat-icon">+</span>
          <span className="ai-search__new-chat-text">新对话</span>
        </button>
        <div className="ai-search__history">
          {sessions.map((session) => {
            const isActive = session.id === activeSessionId;
            const isEditing = session.id === editingSessionId;
            const isConfirmingDelete = confirmingDeleteId === session.id;
            const isDeleting = deletingId === session.id;

            return (
              <motion.div
                key={session.id}
                layout
                className="ai-search__history-row"
                onClick={() => {
                  if (isEditing) return;
                  if (confirmingDeleteId && confirmingDeleteId !== session.id) {
                    cancelDelete();
                  }
                  setActiveSessionId(session.id);
                }}
              >
                <motion.div
                  layout
                  className={`ai-search__history-item ${isActive ? 'active' : ''} ${isEditing ? 'editing' : ''}`}
                  animate={
                    isDeleting
                      ? { x: 20, opacity: 0, transition: { duration: 0.4 } }
                      : {}
                  }
                >
                  {isEditing ? (
                    <input
                      ref={editInputRef}
                      className="ai-search__history-input"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') saveEdit();
                        if (e.key === 'Escape') cancelEdit();
                      }}
                      onClick={(e) => e.stopPropagation()}
                    />
                  ) : (
                    <span className="ai-search__history-title">{session.title}</span>
                  )}

                  {isActive && !isEditing && !isConfirmingDelete && (
                    <span
                      className="ai-search__history-edit"
                      onClick={(e) => {
                        e.stopPropagation();
                        startEdit(session);
                      }}
                    >
                      ✎
                    </span>
                  )}
                  {!isEditing && !isConfirmingDelete && !isDeleting && (
                    <span
                      className="ai-search__history-delete"
                      onClick={(e) => handleFirstDeleteClick(e, session.id)}
                    >
                      ×
                    </span>
                  )}

                  {isEditing && (
                    <span
                      className="ai-search__history-edit"
                      onClick={(e) => {
                        e.stopPropagation();
                        saveEdit();
                      }}
                    >
                      ✓
                    </span>
                  )}
                </motion.div>

                <AnimatePresence>
                  {(isConfirmingDelete || isDeleting) && (
                    <motion.div
                      initial={{ width: 0, opacity: 0, scale: 0.5 }}
                      animate={
                        isDeleting
                          ? { width: 0, opacity: 0, x: 10, transition: { delay: 0.3, duration: 0.2 } }
                          : { width: 28, opacity: 1, scale: 1 }
                      }
                      exit={{ width: 0, opacity: 0, x: 10 }}
                      transition={{ duration: 0.25 }}
                      className="ai-search__trash-btn"
                      onClick={(e: React.MouseEvent) => handleTrashClick(e, session.id)}
                    >
                      <motion.span
                        animate={isDeleting ? { x: [0, -3, 3, -3, 3, 0] } : {}}
                        transition={{ duration: 0.3 }}
                      >
                        🗑️
                      </motion.span>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </div>
        <button
          className={`ai-search__about-btn ${aboutOpen ? 'open' : ''}`}
          data-about-btn
          onClick={onToggleAbout}
        >
          关于本站
        </button>
      </div>
      <AiChatArea
        messages={activeSession.messages}
        onSend={handleSend}
        loading={loading}
        status={activeSession.status}
        onConfirm={handleConfirm}
        onReject={handleReject}
        showConfirm={activeSession.status === 'awaiting_confirmation'}
      />
    </div>
  );
}
