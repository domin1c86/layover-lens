<p align="center">
  <h1 align="center">✈️🚄 中转助手 Layover Lens</h1>
  <p align="center"><em>智能航班与火车中转路线搜索引擎</em></p>
</p>

---

**中转助手（Layover Lens）** 是一个多交通方式的中转路线搜索平台，能够组合航班与火车，为旅客找出城市间的最优中转方案。用户无需分别在各大平台搜索，即可一站式获取按价格、耗时、换乘次数或综合评分排序的最佳路线。

## 系统架构

```
┌──────────────────────────────────────────────────┐
│  前端      React 18 + TypeScript + Vite         │
│           深色模式 · 中英文切换 · motion 动画    │
│           端口 3000                              │
├──────────────────────────────────────────────────┤
│  API 网关  Python FastAPI                        │
│           Pydantic 数据校验 · /api/v1/*          │
│           端口 8000                              │
├──────────────────────────────────────────────────┤
│  规划引擎  C++17 (pybind11) ← 自动切换 → Python │
│           多目标图搜索算法                        │
├──────────────────────────────────────────────────┤
│  数据层    MySQL 8.0 · Mock 适配器               │
│           795 条种子数据（360 航班 + 435 火车）   │
│           覆盖 3 天班期                           │
├──────────────────────────────────────────────────┤
│  AI 助手   DeepSeek 大模型 · 多轮对话会话        │
│           自然语言 → 结构化搜索参数               │
└──────────────────────────────────────────────────┘
```

## 核心功能

- **多目标路线搜索** — 支持价格优先、时间优先、少换乘、综合推荐四种优化策略，每条路线附带评分
- **多模式混合换乘** — 一趟行程可同时包含航班和火车（如：北京飞上海，再乘高铁到杭州）
- **丰富筛选条件** — 出发/到达时间段、价格上限、时长上限、交通工具偏好、排除城市、指定中转城市、是否允许过夜
- **AI 自然语言搜索** — 输入"帮我找下周五北京到昆明最便宜的路线"，AI 通过多轮对话自动补齐搜索参数并确认执行
- **平台标签** — 每条行程段标注数据来源（铁路12306、携程、去哪儿、飞猪）
- **收藏功能** — 收藏心仪路线，本地持久化保存，支持一键取消
- **深色模式与国际化** — 完整中英文界面，CSS 变量驱动的主题系统

## 快速开始（Docker）

```bash
git clone <仓库地址> && cd layover-lens
docker compose up --build
# 前端：http://localhost:3000    后端文档：http://localhost:8000/docs
```

Docker Compose 一键启动三个服务：
- **frontend** — Nginx 静态文件服务 + API 反向代理
- **backend** — FastAPI 应用 + C++ 路线规划引擎
- **mysql** — MySQL 8.0，自动导入 40 个城市、80+ 站点、795 条班次数据

常用命令：
```bash
docker compose up --build          # 完整重建
docker compose restart backend     # 单独重启后端
docker compose down -v && docker compose up --build  # 清空数据库重建
```

## 本地开发

### 前端

```bash
cd frontend
npm install
npm run dev          # Vite 开发服务器，端口 3000，/api 请求代理到 localhost:8000
npm run test         # Vitest 单元测试
npm run build        # TypeScript 类型检查 + 生产构建
```

后端跑在 Docker 而前端本地开发时：
```bash
VITE_PROXY_TARGET=http://localhost:8000 npm run dev
```

### 后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

需要更高规划性能时，编译 C++ 规划引擎：
```bash
cd backend/planner && mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build .
```

### 后端测试

```bash
docker compose exec backend python -m pytest tests/ -v
```

## API 端点

| 方法 | 路径 | 说明 |
|--------|------|-------------|
| `POST` | `/api/v1/search` | 多目标路线搜索 |
| `GET` | `/api/v1/cities` | 城市关键词联想搜索 |
| `POST` | `/api/v1/search/ai/sessions` | 创建 AI 搜索会话 |
| `POST` | `/api/v1/search/ai/sessions/{id}/messages` | 在 AI 会话中发送消息 |
| `POST` | `/api/v1/search/ai/sessions/{id}/confirm` | 确认并执行 AI 搜索 |
| `GET` | `/api/v1/search/ai/sessions/{id}` | 获取 AI 会话状态 |
| `POST` | `/api/v1/auth/login` | 用户登录 |
| `POST` | `/api/v1/auth/register` | 用户注册 |
| `GET` | `/api/v1/user/profile` | 获取当前用户信息 |
| `PATCH` | `/api/v1/user/profile` | 更新用户信息 |
| `GET` | `/api/v1/user/preferences` | 获取用户偏好设置 |
| `PUT` | `/api/v1/user/preferences` | 更新用户偏好设置 |
| `POST` | `/api/v1/favorites` | 收藏路线 |
| `GET` | `/api/v1/favorites` | 查看收藏列表 |
| `DELETE` | `/api/v1/favorites/{id}` | 取消收藏 |
| `GET` | `/health` | 服务健康检查与后端信息 |

完整接口文档：[description/api-interface-list.md](description/api-interface-list.md)

## 配置项

关键环境变量（通过 `docker-compose.yml` 或 `.env` 设置）：

| 变量 | 默认值 | 说明 |
|----------|---------|-------------|
| `DATA_SOURCE` | `mock` | 数据源：`mock`（MySQL 优先 + 内存回退）或 `mysql` |
| `ROUTE_PLANNER_BACKEND` | `auto` | 规划引擎：`python`、`cpp` 或 `auto`（自动检测） |
| `DEEPSEEK_API_KEY` | — | DeepSeek API 密钥，AI 搜索功能必需 |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | AI 搜索使用的模型 |
| `AI_MODEL_PROVIDER` | `deepseek` | Agent 模型提供方：`deepseek`、`openai_compatible` 或 `legacy` |
| `AI_MODEL_API_KEY` | — | `openai_compatible` 提供方的 API 密钥 |
| `AI_MODEL_BASE_URL` | — | `openai_compatible` 提供方的基础地址，不包含 `/chat/completions` |
| `AI_MODEL_NAME` | — | `openai_compatible` 提供方的模型名称 |
| `AI_MODEL_SUPPORTS_JSON_MODE` | `true` | 是否向兼容提供方发送 `response_format: {"type":"json_object"}` |
| `AI_AGENT_TURN_MODE` | `single` | LangGraph Agent 模型调用模式：`dual` 或 `single` |
| `LANGGRAPH_CHECKPOINT_DATABASE_URL` | — | LangGraph PostgreSQL Checkpoint 连接字符串 |
| `LANGGRAPH_AES_KEY` | — | Checkpoint AES 加密密钥，必须为 16、24 或 32 字节 |
| `VITE_AI_SEARCH_ENABLED` | `false` | 构建前端时是否开放 AI 搜索入口 |
| `DATABASE_URL` | — | MySQL 连接字符串 |
| `CORS_ORIGINS` | `["http://localhost:3000", ...]` | 允许的跨域来源 |
| `MAX_ROUTES` | `8` | 每次搜索最多返回的路线数 |
| `DEFAULT_MAX_TRANSFERS` | `2` | 默认最大换乘次数 |

完整配置项参见 [backend/app/config.py](backend/app/config.py)。

## 项目结构

```
layover-lens/
├── frontend/             React 18 + TypeScript + Vite
│   ├── src/
│   │   ├── components/   搜索页、AI搜索页、收藏页、设置面板、顶栏、页脚
│   │   ├── context/      主题、国际化、收藏夹 状态管理
│   │   ├── locales/      中英文翻译词典
│   │   ├── services/     Axios API 请求封装
│   │   ├── styles/       设计变量、样式重置、深色模式
│   │   └── types/        与后端 Schema 对应的 TypeScript 类型
│   └── nginx.conf        生产环境静态文件服务 + API 代理
├── backend/              Python FastAPI
│   ├── app/
│   │   ├── routers/      搜索、城市、认证、用户、预订 路由
│   │   ├── services/     搜索服务、AI 智能体、路线规划器
│   │   ├── data_source/  可插拔数据源适配器（MySQL、内存）
│   │   ├── config.py     pydantic-settings 配置管理
│   │   └── schemas.py    API 请求/响应 Pydantic 模型
│   ├── planner/          C++17 路线规划引擎（pybind11 绑定）
│   └── tests/            后端测试
├── database/             MySQL 建表 + 种子数据
├── description/          项目文档
└── docker-compose.yml    三服务容器编排
```

## 技术栈

**前端：** React 18 · TypeScript · Vite · motion（framer-motion）· Axios · Vitest  
**后端：** Python · FastAPI · Pydantic · MySQL Connector · DeepSeek API · pybind11  
**数据库：** MySQL 8.0 · 40 个城市 · 80+ 站点 · 795 条班次种子数据  
**基础设施：** Docker Compose · Nginx · CMake（C++ 规划引擎编译）

## 许可证

本项目仅用于演示目的。
