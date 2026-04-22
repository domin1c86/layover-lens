from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import cities, search
from app.services import get_search_service

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


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Layover Lens API is running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "data_source": get_search_service().describe_source(),
    }
