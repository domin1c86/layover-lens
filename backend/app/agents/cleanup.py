from __future__ import annotations

import threading
from app.config import settings
from app.agents.search_agent import SearchAgentService
from app.services.user_service import UserService


class AIAgentCleanupWorker:
    def __init__(self, agent_service: SearchAgentService, user_service: UserService) -> None:
        self._agent_service = agent_service
        self._user_service = user_service
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="ai-agent-cleanup", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def run_once(self) -> None:
        try:
            user_ids = self._user_service.list_user_ids_with_ai_sessions()
        except Exception:
            return
        for user_id in user_ids:
            try:
                cleanup_user_ai_sessions(user_id, self._agent_service, self._user_service)
            except Exception:
                continue

    def _run(self) -> None:
        interval = max(settings.ai_agent_cleanup_interval_minutes, 1) * 60
        while not self._stop.is_set():
            self.run_once()
            self._stop.wait(interval)


def cleanup_user_ai_sessions(
    user_id: str,
    agent_service: SearchAgentService,
    user_service: UserService,
) -> None:
    for session_id in user_service.list_expired_ai_session_ids(user_id):
        try:
            agent_service.delete_session(session_id)
        except Exception as exc:
            user_service.queue_ai_checkpoint_deletion(user_id, session_id, str(exc))
        user_service.delete_ai_session(user_id, session_id)
    for session_id in user_service.list_pending_ai_checkpoint_deletions(user_id):
        try:
            agent_service.delete_session(session_id)
            user_service.complete_ai_checkpoint_deletion(session_id)
        except Exception:
            continue
