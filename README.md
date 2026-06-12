<p align="right">
  中文 | <a href="./README_EN.md">English</a>
</p>

<p align="center">
  <h1 align="center">Layover Lens 中转助手</h1>
  <p align="center"><em>面向中国城市间出行的多交通方式路线策略推荐系统</em></p>
</p>

---

Layover Lens 是一个用于验证“城市级交通策略推荐”的开源项目。当前版本不承诺实时票价、实时余票或具体可购买班次，而是根据出发地、目的地、日期和偏好，给出类似 `北京 -> 南京 -> 成都` 的路线策略，并为每一段提供估算费用、估算耗时、服务密度、置信度和外部票务平台查询入口。

项目目标是先跑通搜索体验、C++ 策略算法、AI 参数收集、用户反馈、人工标注和后续训练闭环。未来如果接入真实火车/航班供应商，只需要替换分段数据 provider 和训练数据源，不需要推翻前端和 API 契约。

## 当前状态

- **路线策略推荐**：默认返回城市路径方案，不再主展示具体航班/车次明细。
- **C++ 算法核心**：交通图谱构建、候选召回、分段估算、价格保护和线性排序由 C++17/pybind11 执行。
- **简单线性模型**：当前训练产物是 `linear_ranker_v1.json`，用于控制 C++ 排序权重；暂未实现用户反馈自动改线上参数。
- **Mock / Historical 双数据模式**：无训练产物时使用 mock 数据；存在历史 CSV/XLSX 构建产物时可切换到 historical dataset。
- **AI 对话搜索**：基于 LangGraph，逐步收集出发地、目的地、日期等条件，用户确认后执行策略搜索。
- **Agent 工具**：支持日期、天气、真实 POI 查询；POI 以高德为主、百度兜底，并带轻量 RAG 缓存。
- **账号安全**：支持真实注册登录、HttpOnly Cookie 会话、CSRF、设备管理、TOTP 双重验证和“使用 2FA 替代邮件验证码”。
- **前端体验**：普通搜索、AI 搜索、收藏、本地头像、主题切换、中英文、路线评价和外部票务跳转提醒。
- **反馈闭环基础**：路线评价可匿名或登录提交到 MySQL，支持后续人工标注和训练样本导出。

## 架构概览

```text
React 18 + TypeScript + Vite frontend (:3000)
  -> Axios API client
  -> Nginx / Vite proxy for /api

FastAPI backend (:8000)
  -> auth / user / cities / search routers
  -> SearchService 调用 C++ 路线策略 planner
  -> LangGraph Agent + tools + checkpoint storage

C++ planner module
  -> TrafficGraphBuilder
  -> CandidateRetriever
  -> RankingModel
  -> pybind11 bindings

MySQL 8.0
  -> 用户、会话、设备、偏好、收藏
  -> mock catalog、POI cache、路线反馈、训练元数据

PostgreSQL
  -> LangGraph checkpoint storage
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
- 健康检查：`http://localhost:8000/health`

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

本地后端环境使用 Python 3.10.11 生成的 `.venv310`：

```powershell
cd backend
.\.venv310\Scripts\python.exe -m pytest tests -q
.\.venv310\Scripts\python.exe -m uvicorn app.main:app --reload
```

修改 `backend/planner/` 后需要重新构建 C++ planner：

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

所有前端可见文案需要进入 `frontend/src/locales`，并保持中英文 key 镜像。

## 路线训练数据与模型

训练目录：

```text
backend/data/route_training/
  raw_csv/       # 原始 CSV/XLSX，默认不提交 Git
  artifacts/     # 聚合后的交通图谱产物
  models/        # 线性排序模型权重
```

当前线上搜索至少需要两个产物：

- `backend/data/route_training/artifacts/route_edges_v1.json.gz`
- `backend/data/route_training/models/linear_ranker_v1.json`

构建和检查：

```powershell
cd backend
.\.venv310\Scripts\python.exe -m app.cli.route_training init
.\.venv310\Scripts\python.exe -m app.cli.route_training status
.\.venv310\Scripts\python.exe -m app.cli.route_training build
.\.venv310\Scripts\python.exe -m app.cli.route_training validate
.\.venv310\Scripts\python.exe -m app.cli.route_training evaluate
```

`ROUTE_DATASET_MODE=auto` 时，系统会优先使用可用 historical artifact；没有 artifact 时回退到 mock。也可以显式设置：

- `ROUTE_DATASET_MODE=mock`
- `ROUTE_DATASET_MODE=historical`

训练产物默认被 `.gitignore` 忽略。如果希望开源版本开箱即用，可以强制提交压缩后的 artifact 和模型文件，但不要提交原始 CSV/XLSX：

```powershell
git add -f backend/data/route_training/artifacts/route_edges_v1.json.gz
git add -f backend/data/route_training/models/linear_ranker_v1.json
```

如果未来 artifact 体积明显变大，建议改用 GitHub Release、Git LFS、DVC 或对象存储。

## 反馈与自进化边界

当前已经有反馈收集能力：

- 普通搜索路线卡评价。
- AI 搜索体验评价。
- 匿名反馈和登录用户反馈。
- 四项五星评分、文本评论、采用方案、多选方案、点击平台、搜索请求快照和推荐结果快照。
- 后端保存 `dataset_version` 和 `model_version`，便于回溯模型表现。

当前还没有开启“用户反馈实时修改线上参数”。推荐路线是：

```text
route_feedback / route_feedback_annotations
  -> 清洗有效样本
  -> 人工或规则生成标签
  -> 离线训练候选模型
  -> evaluate 对比旧模型
  -> 人工确认发布
```

少量反馈不适合自动调参，因为噪声较大。第一版应保持“离线训练、离线评估、手动发布、可回滚”。

## API 清单

完整接口文档见 [description/api-interface-list.md](./description/api-interface-list.md)。

常用入口：

| Method | Path | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 服务、数据源、planner、AI、POI 和训练产物摘要 |
| `GET` | `/api/v1/cities` | 城市列表和关键词过滤 |
| `POST` | `/api/v1/search` | 路线策略搜索 |
| `POST` | `/api/v1/search/feedback` | 路线评价，支持匿名提交 |
| `GET` | `/api/v1/search/feedback/annotated` | 导出已标注反馈样本 |
| `POST` | `/api/v1/search/ai/sessions/stream` | 创建 AI 会话并流式返回 |
| `POST` | `/api/v1/search/ai/sessions/{session_id}/confirm/stream` | 确认 AI 搜索并流式返回结果 |
| `GET` | `/api/v1/search/ai/memory` | 读取 Agent 长期记忆 |
| `DELETE` | `/api/v1/search/ai/memory/{memory_key}` | 删除单条 Agent 长期记忆 |
| `POST` | `/api/v1/auth/register` | 注册并设置会话 Cookie |
| `POST` | `/api/v1/auth/login` | 登录，可能返回 TOTP challenge |
| `POST` | `/api/v1/auth/logout` | 退出登录 |
| `GET` | `/api/v1/user/profile` | 当前用户资料 |
| `PUT` | `/api/v1/user/profile` | 修改用户资料 |
| `GET` | `/api/v1/user/devices` | 登录设备列表 |
| `POST` | `/api/v1/user/totp/setup` | 创建 TOTP 绑定信息 |
| `POST` | `/api/v1/user/totp/enable` | 启用 TOTP |
| `POST` | `/api/v1/user/totp/disable` | 关闭 TOTP |

## 关键环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `development` | `development` 或 `production` |
| `DATABASE_URL` | compose 中配置 | MySQL 连接字符串 |
| `ROUTE_PLANNER_BACKEND` | `auto` | `cpp`、`python` 或 `auto` |
| `ROUTE_TRAINING_DATA_DIR` | `backend/data/route_training` | CSV、artifact 和模型目录 |
| `ROUTE_DATASET_MODE` | `auto` | `auto`、`mock` 或 `historical` |
| `SESSION_COOKIE_SECURE` | 本地为 `false` | 生产 HTTPS 下应为 `true` |
| `CSRF_SECRET` | dev 默认值 | 生产必须替换 |
| `TOTP_ENCRYPTION_SECRET` | dev 默认值 | 生产必须替换 |
| `VITE_AI_SEARCH_ENABLED` | `false` | 前端是否开放 AI 搜索入口 |
| `AI_MODEL_PROVIDER` | `deepseek` | Agent 模型提供方 |
| `DEEPSEEK_API_KEY` | 空 | DeepSeek API Key |
| `AI_AGENT_TURN_MODE` | `single` | Agent 单调用 / 双调用模式 |
| `LANGGRAPH_CHECKPOINT_DATABASE_URL` | compose 中配置 | LangGraph PostgreSQL checkpoint |
| `AMAP_WEB_SERVICE_KEY` | 空 | 高德 Web 服务 Key |
| `BAIDU_MAP_WEB_SERVICE_AK` | 空 | 百度地图 Web 服务 AK |
| `AI_AGENT_POI_DUAL_VERIFY_ENABLED` | `false` | 是否启用高德/百度双源 POI 验证 |

更多配置以 [backend/app/config.py](./backend/app/config.py) 为准。

## 项目结构

```text
frontend/                         React + TypeScript + Vite
backend/app/                      FastAPI routers, services, schemas, agents
backend/planner/                  C++17 planner and pybind11 bindings
backend/data/route_training/      训练数据、artifact、模型权重
database/init.sql                 MySQL 初始化脚本
description/                      设计和 API 文档
docker-compose.yml                本地编排
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

当前路线策略基于 mock 数据或离线 CSV/XLSX 聚合估算，不代表实时票价、实时余票或可购买班次。外部平台按钮只作为分段查询入口；最终价格、余票、退改签和购票规则以外部平台为准。

## License

本项目目前用于学习、演示和内测验证。
