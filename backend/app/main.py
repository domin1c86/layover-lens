from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, bookings, cities, search, user
from app.agents.search_agent import get_search_agent_service
from app.services import get_search_service

if settings.app_env.lower() == "production":
    if "*" in settings.cors_origins or not settings.cors_origins:
        raise RuntimeError("Production CORS_ORIGINS must be an explicit allowlist.")

app = FastAPI(
    title=settings.app_name,
    description="中转助手 - 多交通方式路径规划 API",
    version=settings.app_version,
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
def health_check() -> dict[str, str]:
    search_service = get_search_service()
    agent_service = get_search_agent_service()
    return {
        "status": "ok",
        "data_source": search_service.describe_source(),
        "planner_backend": search_service.describe_planner(),
        "ai_search_backend": agent_service.describe_backend(),
    }
