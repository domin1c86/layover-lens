import { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import type { AiSessionResponse, AiSessionStatus, AiStreamEvent, SearchRequest } from '../../types';
import { aiSearchApi } from '../../services/api';
import { AI_SEARCH_ENABLED } from '../../config/features';
import { useLocale } from '../../context/LocaleContext';
import { useAuth } from '../../context/AuthContext';
import { Icon } from '../../icons';
import AiChatArea, { type AiChatMessage } from './AiChatArea';
import './AiSearchTab.css';

interface Session {
  id: string;
  sessionId: string | null;
  messages: AiChatMessage[];
  status: AiSessionStatus | 'idle';
  finalRequest: SearchRequest | null;
  title: string;
  readyForConfirmation: boolean;
  loaded: boolean;
}

interface AiSearchTabProps {
  aboutOpen?: boolean;
  onToggleAbout?: () => void;
}

let nextSessionId = 1;

function createEmptySession(title: string): Session {
  return {
    id: `local-${nextSessionId++}`,
    sessionId: null,
    messages: [],
    status: 'idle',
    finalRequest: null,
    title,
    readyForConfirmation: false,
    loaded: true,
  };
}

function messagesFromResponse(response: AiSessionResponse): AiChatMessage[] {
  return response.conversation.map((message) => ({
    role: message.role,
    content: message.content,
    isSearchResult: Boolean(message.search_response),
    searchData: message.search_response || undefined,
    finalRequest: message.search_response ? response.final_request || undefined : undefined,
    toolResults: message.tool_results || undefined,
  }));
}

export default function AiSearchTab({ aboutOpen, onToggleAbout }: AiSearchTabProps) {
  const { lang, t } = useLocale();
  const { isLoggedIn } = useAuth();
  const [sessions, setSessions] = useState<Session[]>(() => [createEmptySession(t('aiChat.newChat'))]);
  const [activeSessionId, setActiveSessionId] = useState(sessions[0].id);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [mobileHistoryOpen, setMobileHistoryOpen] = useState(false);
  const [mobileToolsCollapsed, setMobileToolsCollapsed] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const activeSession = sessions.find((session) => session.id === activeSessionId) || sessions[0];

  const updateSession = useCallback((id: string, partial: Partial<Session>) => {
    setSessions((previous) => previous.map((session) => (
      session.id === id ? { ...session, ...partial } : session
    )));
  }, []);

  useEffect(() => {
    if (!AI_SEARCH_ENABLED || !isLoggedIn) return;
    let cancelled = false;
    aiSearchApi.listSessions()
      .then((history) => {
        if (cancelled) return;
        setSessions((current) => {
          const localEmpty = current.find((session) => !session.sessionId && session.messages.length === 0);
          const restored = history.map((item): Session => {
            const existing = current.find((session) => session.sessionId === item.session_id);
            return existing ? { ...existing, title: item.title, status: item.status } : {
              id: item.session_id,
              sessionId: item.session_id,
              messages: [],
              status: item.status,
              finalRequest: null,
              title: item.title,
              readyForConfirmation: false,
              loaded: false,
            };
          });
          return localEmpty ? [localEmpty, ...restored] : restored;
        });
      })
      .catch(() => setError(t('aiChat.historyLoadFailed')));
    return () => {
      cancelled = true;
    };
  }, [isLoggedIn, t]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const applyResponse = useCallback((id: string, response: AiSessionResponse) => {
    updateSession(id, {
      sessionId: response.session_id,
      messages: messagesFromResponse(response),
      status: response.status,
      finalRequest: response.final_request,
      readyForConfirmation: response.ready_for_confirmation,
      loaded: true,
    });
  }, [updateSession]);

  const loadSession = async (session: Session) => {
    setActiveSessionId(session.id);
    setMobileHistoryOpen(false);
    setError('');
    if (!session.sessionId || session.loaded) return;
    setLoading(true);
    try {
      applyResponse(session.id, await aiSearchApi.getSession(session.sessionId));
    } catch {
      setError(t('aiChat.historyLoadFailed'));
    } finally {
      setLoading(false);
    }
  };

  const handleStreamEvent = useCallback((id: string, event: AiStreamEvent) => {
    if (event.event === 'assistant_delta') {
      setSessions((previous) => previous.map((session) => {
        if (session.id !== id) return session;
        const messages = [...session.messages];
        const last = messages[messages.length - 1];
        if (last?.role === 'assistant' && last.streaming) {
          messages[messages.length - 1] = { ...last, content: last.content + event.delta };
        } else {
          messages.push({ role: 'assistant', content: event.delta, streaming: true });
        }
        return { ...session, messages };
      }));
    }
    if (event.event === 'status') updateSession(id, { status: event.status });
    if (event.event === 'tool_result') {
      setSessions((previous) => previous.map((session) => {
        if (session.id !== id) return session;
        const messages = [...session.messages];
        const last = messages[messages.length - 1];
        if (last?.role === 'assistant' && last.streaming) {
          messages[messages.length - 1] = {
            ...last,
            toolResults: [...(last.toolResults || []), event.tool_result],
          };
        } else {
          messages.push({
            role: 'assistant',
            content: '',
            toolResults: [event.tool_result],
            streaming: true,
          });
        }
        return { ...session, messages };
      }));
    }
    if (event.event === 'done') applyResponse(id, event.response);
  }, [applyResponse, t, updateSession]);

  const runStream = useCallback(async (
    id: string,
    execute: (onEvent: (event: AiStreamEvent) => void, signal: AbortSignal) => Promise<void>
  ) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError('');
    try {
      await execute((event) => handleStreamEvent(id, event), controller.signal);
    } catch (streamError) {
      if (!controller.signal.aborted) {
        const message = streamError instanceof Error ? streamError.message : '';
        setError(message.includes('ai_storage_guard_active') ? t('aiChat.storageGuard') : t('aiChat.requestFailed'));
        try {
          const session = sessions.find((item) => item.id === id);
          if (session?.sessionId) applyResponse(id, await aiSearchApi.getSession(session.sessionId));
        } catch {
          // The latest checkpoint may not exist when the initial request failed.
        }
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setLoading(false);
    }
  }, [applyResponse, handleStreamEvent, sessions, t]);

  const handleSend = useCallback(async (text: string) => {
    if (!AI_SEARCH_ENABLED) return;
    if (activeSession.status === 'blocked') return;
    if (!isLoggedIn) {
      setError(t('aiChat.loginRequired'));
      return;
    }
    const id = activeSession.id;
    updateSession(id, { messages: [...activeSession.messages, { role: 'user', content: text }] });
    if (activeSession.sessionId) {
      await runStream(id, (onEvent, signal) => (
        aiSearchApi.streamMessage(activeSession.sessionId as string, text, lang, onEvent, signal)
      ));
    } else {
      await runStream(id, (onEvent, signal) => aiSearchApi.streamCreate(text, lang, onEvent, signal));
    }
  }, [activeSession, isLoggedIn, lang, runStream, t, updateSession]);

  const handleConfirm = useCallback(async () => {
    if (!activeSession.sessionId) return;
    await runStream(activeSession.id, (onEvent, signal) => (
      aiSearchApi.streamConfirm(activeSession.sessionId as string, true, lang, onEvent, signal)
    ));
  }, [activeSession, lang, runStream]);

  const handleReject = useCallback(async () => {
    if (!activeSession.sessionId) return;
    await runStream(activeSession.id, (onEvent, signal) => (
      aiSearchApi.streamConfirm(activeSession.sessionId as string, false, lang, onEvent, signal)
    ));
  }, [activeSession, lang, runStream]);

  const newChat = () => {
    const existing = sessions.find((session) => !session.sessionId && session.messages.length === 0);
    if (existing) {
      setActiveSessionId(existing.id);
      setMobileHistoryOpen(false);
      return;
    }
    const session = createEmptySession(t('aiChat.newChat'));
    setSessions((previous) => [session, ...previous]);
    setActiveSessionId(session.id);
    setMobileHistoryOpen(false);
  };

  const saveEdit = async (session: Session) => {
    const title = editTitle.trim();
    setEditingSessionId(null);
    if (!title) return;
    updateSession(session.id, { title });
    if (!session.sessionId) return;
    try {
      await aiSearchApi.renameSession(session.sessionId, title);
    } catch {
      setError(t('aiChat.renameFailed'));
    }
  };

  const deleteSession = async (session: Session) => {
    if (session.sessionId) {
      try {
        await aiSearchApi.deleteSession(session.sessionId);
      } catch {
        setError(t('aiChat.deleteFailed'));
        return;
      }
    }
    const remaining = sessions.filter((item) => item.id !== session.id);
    const nextSessions = remaining.length > 0 ? remaining : [createEmptySession(t('aiChat.newChat'))];
    setSessions(nextSessions);
    if (activeSessionId === session.id) setActiveSessionId(nextSessions[0].id);
  };

  const renderSessionRow = (session: Session) => (
    <motion.div layout key={session.id} className="ai-search__history-row">
      <div
        className={`ai-search__history-item ${session.id === activeSessionId ? 'active' : ''}`}
        onClick={() => loadSession(session)}
      >
        {editingSessionId === session.id ? (
          <input
            autoFocus
            className="ai-search__history-input"
            value={editTitle}
            onChange={(event) => setEditTitle(event.target.value)}
            onBlur={() => saveEdit(session)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') saveEdit(session);
              if (event.key === 'Escape') setEditingSessionId(null);
            }}
            onClick={(event) => event.stopPropagation()}
          />
        ) : (
          <span className="ai-search__history-title">{session.title}</span>
        )}
        {session.sessionId ? (
          <>
            <button
              className="ai-search__history-edit"
              aria-label={t('aiChat.rename')}
              onClick={(event) => {
                event.stopPropagation();
                setEditingSessionId(session.id);
                setEditTitle(session.title);
              }}
            >
              <Icon name="actions.edit" />
            </button>
            <button
              className="ai-search__history-delete"
              aria-label={t('aiChat.delete')}
              onClick={(event) => {
                event.stopPropagation();
                deleteSession(session);
              }}
            >
              <Icon name="actions.deleteX" />
            </button>
          </>
        ) : null}
      </div>
    </motion.div>
  );

  return (
    <div className={`ai-search ${mobileToolsCollapsed ? 'ai-search--mobile-tools-collapsed' : ''}`}>
      <div className="ai-search__sidebar">
        <button className="ai-search__new-chat" onClick={newChat}>
          <span className="ai-search__new-chat-icon"><Icon name="actions.add" /></span>
          <span className="ai-search__new-chat-text">{t('aiChat.newChat')}</span>
        </button>
        <div className="ai-search__history">
          {sessions.map(renderSessionRow)}
        </div>
        <button
          className={`ai-search__about-btn ${aboutOpen ? 'open' : ''}`}
          data-about-btn
          onClick={onToggleAbout}
        >
          {t('aiChat.about')}
        </button>
      </div>
      <button
        type="button"
        className={`ai-search__mobile-toolbar-toggle ${mobileToolsCollapsed ? 'collapsed' : ''}`}
        aria-label={mobileToolsCollapsed ? (lang === 'en' ? 'Expand AI tools' : '展开 AI 工具') : (lang === 'en' ? 'Collapse AI tools' : '收起 AI 工具')}
        onClick={() => setMobileToolsCollapsed((previous) => !previous)}
      >
        <span aria-hidden="true">{mobileToolsCollapsed ? '+' : '−'}</span>
      </button>
      <AnimatePresence initial={false}>
        {!mobileToolsCollapsed ? (
          <motion.div
            className="ai-search__mobile-toolbar"
            initial={{ opacity: 0, y: -10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.98 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
          >
            <button type="button" onClick={newChat}>
              <Icon name="actions.add" />
              <span>{t('aiChat.newChat')}</span>
            </button>
            <button type="button" onClick={() => setMobileHistoryOpen(true)}>
              <Icon name="nav.hamburger" />
              <span>{lang === 'en' ? 'History' : '历史'}</span>
            </button>
            <button
              type="button"
              className={`ai-search__mobile-about-button ${aboutOpen ? 'active' : ''}`}
              data-about-btn
              aria-label={t('aiChat.about')}
              title={t('aiChat.about')}
              onClick={onToggleAbout}
            >
              <span aria-hidden="true">?</span>
            </button>
          </motion.div>
        ) : null}
      </AnimatePresence>
      {mobileHistoryOpen ? (
        <div className="ai-search__history-sheet" onClick={() => setMobileHistoryOpen(false)}>
          <div className="ai-search__history-sheet-panel" onClick={(event) => event.stopPropagation()}>
            <div className="ai-search__history-sheet-head">
              <strong>{lang === 'en' ? 'Conversation history' : '会话历史'}</strong>
              <button type="button" onClick={() => setMobileHistoryOpen(false)} aria-label="Close">×</button>
            </div>
            <div className="ai-search__history ai-search__history--sheet">
              {sessions.map(renderSessionRow)}
            </div>
          </div>
        </div>
      ) : null}
      <AiChatArea
        messages={activeSession.messages}
        onSend={handleSend}
        loading={loading}
        status={activeSession.status}
        onConfirm={handleConfirm}
        onReject={handleReject}
        showConfirm={activeSession.readyForConfirmation && activeSession.status !== 'blocked'}
        disabled={!AI_SEARCH_ENABLED}
        error={error}
      />
    </div>
  );
}
