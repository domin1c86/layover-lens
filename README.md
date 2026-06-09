<p align="right">
  中文 | <a href="./README_EN.md">English</a>
</p>

<p align="center">
  <h1 align="center">Layover Lens 中转助手</h1>
  <p align="center"><em>面向中国城市间出行的多交通方式路线策略推荐系统</em></p>
</p>

---

Layover Lens 是一个用于验证“城市级交通策略推荐”的开源项目。当前版本不承诺实时票价、实时余票或具体可购买班次，而是根据出发地、目的地、日期和偏好，给出类似 `北京 -> 南京 -> 成都` 的路线策略，并为每一段提供估算费用、估算耗时、服务密度、置信度和外部票务平台查询入口。

项目目标是先把搜索体验、策略算法、AI 参数收集、反馈标注和未来训练闭环跑通；后续如果接入真实火车/航班供应商，只需要替换分段 provider 和训练数据源，不需要推翻前端和 API 契约。

## 当前能力

- **路线策略推荐**：默认返回城市路径方案，不再主展示具体班次明细。
- **C++ 算法核心**：交通图谱构建、候选召回、分段估算、价格保护和线性排序均由 C++17/pybind11 执行。
- **Mock 与历史 CSV 双数据模式**：无 CSV 时使用当前 mock 数据；有离线构建产物时可使用历史 CSV 聚合图谱和线性权重模型。
- **AI 对话搜索**：基于 LangGraph 架构，逐步收集出发地、目的地、日期等必要参数，用户确认后执行策略搜索。
- **模型适配器**：支持 DeepSeek，并预留 OpenAI-compatible HTTP 直连模型适配。
- **Agent 工具**：支持日期、天气、真实 POI 查询工具；POI 以高德为主、百度兜底，并带轻量 RAG 缓存。
- **账号系统**：后端真实注册、登录、退出、HttpOnly Cookie 会话、CSRF、设备管理、TOTP 双重验证。
- **前端体验**：普通搜索、AI 搜索、收藏、本地头像、主题切换、中英文、路线评价和外部票务跳转提醒。
- **反馈闭环**：路线评价可匿名提交到 MySQL，支持后续人工标注和模型训练数据导出。

## 架构概览

```text
React 18 + TypeScript + Vite frontend (:3000)
  -> Axios / fetch API client
  -> Nginx / Vite proxy for /api

FastAPI backend (:8000)
  -> auth / user / cities / search / bookings routers
  -> SearchService orchestrates route strategy search
  -> LangGraph-based AI agent with tools and checkpoint storage

C++ planner module
  -> TrafficGraphBuilder
  -> CandidateRetriever
  -> RankingModel
  -> pybind11 bindings used by Python wrapper

MySQL 8.0
  -> users, auth tokens, devices, preferences
  -> mock catalog data, favorites, route feedback
  -> POI cache and training metadata

PostgreSQL
  -> LangGraph checkpoint storage for AI sessions
```

## 快速开始

```powershell
git clone <repo-url>
cd layover-lens
docker compose up --build -d backend frontend
```

访问地址：

- 前端：`http://localhost:3000`
- 后端 Swagger：`http://localhost:8000/docs`
- 后端健康检查：`http://localhost:8000/health`

常用命令：

```powershell
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose exec -T backend python -m pytest tests/ -q
```

不要随意运行 `docker compose down -v`，它会删除数据库 volume。

## 本地开发

### 后端

本地后端环境统一使用 Python 3.10.11 生成的虚拟环境：

```powershell
cd backend
.\.venv310\Scripts\python.exe -m pytest tests -q
.\.venv310\Scripts\python.exe -m uvicorn app.main:app --reload
```

修改 C++ planner 后需要重新构建：

```powershell
cd backend\planner
cmake -S . -B build
cmake --build build --config Release
```

### 前端

```powershell
cd frontend
npm install
npm run dev
npm run test
npm run build
```

## 历史 CSV 与路线训练

训练数据目录位于：

```text
backend/data/route_training/
  raw_csv/       # 放原始 CSV，已被 gitignore 忽略
  artifacts/     # 离线聚合图谱产物
  models/        # 线性排序模型权重
```

初始化与构建：

```powershell
cd backend
.\.venv310\Scripts\python.exe -m app.cli.route_training init
.\.venv310\Scripts\python.exe -m app.cli.route_training status
.\.venv310\Scripts\python.exe -m app.cli.route_training build
```

当没有 CSV 或离线产物时，系统继续使用 mock 数据。当存在可用 artifact 和模型权重时，搜索会切换到 historical dataset，并在响应中返回 `route_dataset_mode`、`route_dataset_version` 和 `route_model_version`。

## API 清单

完整接口清单见 [description/api-interface-list.md](./description/api-interface-list.md)。

常用入口：

| Method | Path | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 服务、数据源、Planner、AI 和 POI 能力摘要 |
| `GET` | `/api/v1/cities` | 城市列表和关键词过滤 |
| `POST` | `/api/v1/search` | 路线策略搜索 |
| `POST` | `/api/v1/search/feedback` | 路线评价，支持匿名提交 |
| `POST` | `/api/v1/search/ai/sessions/stream` | 创建 AI 会话并流式返回 |
| `POST` | `/api/v1/search/ai/sessions/{session_id}/confirm/stream` | 确认 AI 搜索并流式返回结果 |
| `POST` | `/api/v1/auth/register` | 注册并设置会话 Cookie |
| `POST` | `/api/v1/auth/login` | 登录，可能返回 TOTP challenge |
| `GET` | `/api/v1/user/profile` | 当前用户资料 |
| `GET` | `/api/v1/user/devices` | 登录设备列表 |

## 关键环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `development` | `development` 或 `production` |
| `DATABASE_URL` | compose 中配置 | MySQL 连接字符串 |
| `ROUTE_PLANNER_BACKEND` | `auto` | `cpp`、`python` 或 `auto`；默认搜索应使用 C++ 策略 planner |
| `ROUTE_TRAINING_DATA_DIR` | `backend/data/route_training` | CSV、artifact 和模型权重目录 |
| `ROUTE_DATASET_MODE` | `auto` | `auto`、`mock` 或 `historical` |
| `SESSION_COOKIE_SECURE` | 本地为 `false` | 生产 HTTPS 下应为 `true` |
| `VITE_AI_SEARCH_ENABLED` | `false` | 前端是否开放 AI 搜索入口 |
| `AI_MODEL_PROVIDER` | `deepseek` | Agent 模型提供方 |
| `DEEPSEEK_API_KEY` | 空 | DeepSeek API Key |
| `AI_AGENT_TURN_MODE` | `single` | Agent 单调用/双调用模式 |
| `LANGGRAPH_CHECKPOINT_DATABASE_URL` | compose 中配置 | LangGraph PostgreSQL checkpoint |
| `AMAP_WEB_SERVICE_KEY` | 空 | 高德 Web 服务 Key |
| `BAIDU_MAP_WEB_SERVICE_AK` | 空 | 百度地图 Web 服务 AK |
| `AI_AGENT_POI_DUAL_VERIFY_ENABLED` | `false` | 是否启用高德/百度双源 POI 验证 |

更多配置以 [backend/app/config.py](./backend/app/config.py) 为准。

## 项目结构

```text
frontend/                 React + TypeScript + Vite
backend/app/              FastAPI routers, services, schemas, agents
backend/planner/          C++17 planner and pybind11 bindings
backend/data/route_training/
database/init.sql         MySQL 初始化脚本
description/              设计与接口文档
docker-compose.yml        本地编排
```

## 测试

```powershell
cd backend
.\.venv310\Scripts\python.exe -m pytest tests -q

cd ..\frontend
npm run test
npm run build

cd ..
docker compose up --build -d backend frontend
docker compose exec -T backend python -m pytest tests/ -q
```

## 数据与免责声明

当前路线策略仍基于 mock 数据或离线 CSV 聚合估算，不代表实时票价、实时余票或可购买班次。外部平台按钮只作为分段查询入口，最终价格、余票、退改签和购票规则以外部平台为准。

## License

本项目目前用于学习、演示和内测验证。
