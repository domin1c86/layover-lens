from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import search, cities

app = FastAPI(
    title="Layover Lens API",
    description="中转助手 - 智能交通路线规划",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(search.router, prefix="/api/v1", tags=["search"])
app.include_router(cities.router, prefix="/api/v1", tags=["cities"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
