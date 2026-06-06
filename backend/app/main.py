from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.cleanup import AIAgentCleanupWorker
from app.agents.search_agent import get_search_agent_service
from app.config import settings
from app.routers import auth, bookings, cities, search, user
from app.services import get_search_service, get_user_service

if settings.app_env.lower() == "production":
    if "*" in settings.cors_origins or not settings.cors_origins:
        raise RuntimeError("Production CORS_ORIGINS must be an explicit allowlist.")

_cleanup_worker: AIAgentCleanupWorker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    del app
    global _cleanup_worker
    _cleanup_worker = AIAgentCleanupWorker(get_search_agent_service(), get_user_service())
    _cleanup_worker.start()
    try:
        yield
    finally:
        if _cleanup_worker is not None:
            _cleanup_worker.stop()


app = FastAPI(
    title=settings.app_name,
    description="Layover Lens multimodal route planning API",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router, prefix=settings.api_v1_prefix, tags=["search"])
app.include_router(cities.router, prefix=settings.api_v1_prefix, tags=["cities"])
app.include_router(auth.router, prefix=settings.api_v1_prefix, tags=["auth"])
app.include_router(user.router, prefix=settings.api_v1_prefix, tags=["user"])
app.include_router(bookings.router, prefix=settings.api_v1_prefix, tags=["bookings"])


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Layover Lens API is running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health_check() -> dict[str, str | int | bool]:
    search_service = get_search_service()
    agent_service = get_search_agent_service()
    return {
        "status": "ok",
        "data_source": search_service.describe_source(),
        "planner_backend": search_service.describe_planner(),
        "ai_search_backend": agent_service.describe_backend(),
        "ai_streaming": "reply",
        "ai_tools_enabled": settings.ai_agent_tools_enabled,
        "ai_chat_retention_days": settings.ai_chat_retention_days,
        "ai_agent_max_sessions": settings.ai_agent_max_sessions,
        "ai_storage_guard_disabled_writes": settings.ai_agent_storage_disable_new_writes,
        "ai_storage_soft_limit_mb": settings.ai_agent_storage_soft_limit_mb,
        "ai_poi_enabled": settings.ai_agent_poi_enabled,
        "ai_poi_primary_provider": settings.ai_agent_poi_primary_provider,
        "ai_poi_dual_verify_enabled": settings.ai_agent_poi_dual_verify_enabled,
        "ai_poi_quota_mode": "configured",
    }
