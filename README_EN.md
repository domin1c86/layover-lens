<p align="right">
  <a href="./README.md">中文</a> | English
</p>

<p align="center">
  <h1 align="center">Layover Lens</h1>
  <p align="center"><em>A multimodal route strategy recommendation system for intercity travel in China</em></p>
</p>

---

Layover Lens is an open-source project for validating city-level transportation strategy recommendations. The current version does not promise realtime fares, realtime inventory, or purchasable schedules. Instead, it returns route strategies such as `Beijing -> Nanjing -> Chengdu`, with estimated cost, estimated duration, service density, confidence, and external ticket-search entry points for each segment.

The goal is to validate the search experience, strategy algorithm, AI parameter collection, feedback annotation, and future training loop first. If realtime train or flight providers are added later, the segment provider and training data source can be replaced without rebuilding the frontend or API contract.

## Current Capabilities

- **Route strategy recommendations**: default search returns city-path strategies instead of detailed schedules.
- **C++ algorithm core**: traffic graph construction, candidate retrieval, segment estimation, direct-price guardrails, and linear ranking are implemented in C++17 through pybind11.
- **Mock and historical CSV modes**: mock data is used when no CSV artifact is available; historical CSV artifacts can drive graph features and linear ranker weights.
- **AI conversational search**: LangGraph-based agent collects required fields such as origin, destination, and date, then executes search after user confirmation.
- **Model adapters**: DeepSeek is supported, with an OpenAI-compatible HTTP adapter kept for other providers.
- **Agent tools**: date, weather, and real POI tools. POI search uses Amap first and Baidu as fallback, with a lightweight RAG cache.
- **Account system**: real backend registration, login, logout, HttpOnly cookie sessions, CSRF, device management, and TOTP 2FA.
- **Frontend experience**: regular search, AI search, favorites, local avatars, theme switching, Chinese/English UI, route feedback, and external ticket-link warnings.
- **Feedback loop**: anonymous route feedback can be stored in MySQL for later manual annotation and model training.

## Architecture

```text
React 18 + TypeScript + Vite frontend (:3200)
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

## Quick Start

```powershell
git clone <repo-url>
cd layover-lens
docker compose up --build -d backend frontend
```

URLs:

- Frontend: `http://localhost:3200`
- Backend Swagger: `http://localhost:8000/docs`
- Backend health: `http://localhost:8000/health`

Useful commands:

```powershell
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose exec -T backend python -m pytest tests/ -q
```

Avoid running `docker compose down -v` unless you intentionally want to delete database volumes.

## Local Development

### Backend

Local backend development uses a Python 3.10.11 virtual environment:

```powershell
cd backend
.\.venv310\Scripts\python.exe -m pytest tests -q
.\.venv310\Scripts\python.exe -m uvicorn app.main:app --reload
```

Rebuild the C++ planner after changing `backend/planner/`:

```powershell
cd backend\planner
cmake -S . -B build
cmake --build build --config Release
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
npm run test
npm run build
```

## Historical CSV and Route Training

Training data lives under:

```text
backend/data/route_training/
  raw_csv/       # raw CSV files, ignored by git
  artifacts/     # offline aggregated graph artifacts
  models/        # linear ranker weight files
```

Initialize and build:

```powershell
cd backend
.\.venv310\Scripts\python.exe -m app.cli.route_training init
.\.venv310\Scripts\python.exe -m app.cli.route_training status
.\.venv310\Scripts\python.exe -m app.cli.route_training build
```

When no CSV or artifact is available, the system keeps using mock data. When a valid artifact and model file exist, search switches to the historical dataset and returns `route_dataset_mode`, `route_dataset_version`, and `route_model_version`.

## API List

Full API list: [description/api-interface-list.md](./description/api-interface-list.md).

Common endpoints:

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Service, data source, planner, AI, and POI capability summary |
| `GET` | `/api/v1/cities` | City list and keyword filtering |
| `POST` | `/api/v1/search` | Route strategy search |
| `POST` | `/api/v1/search/feedback` | Route feedback, supports anonymous submission |
| `POST` | `/api/v1/search/ai/sessions/stream` | Create an AI session and stream response |
| `POST` | `/api/v1/search/ai/sessions/{session_id}/confirm/stream` | Confirm AI search and stream results |
| `POST` | `/api/v1/auth/register` | Register and set session cookies |
| `POST` | `/api/v1/auth/login` | Login, may return a TOTP challenge |
| `GET` | `/api/v1/user/profile` | Current user profile |
| `GET` | `/api/v1/user/devices` | Login device list |

## Key Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `APP_ENV` | `development` | `development` or `production` |
| `DATABASE_URL` | set in compose | MySQL connection string |
| `ROUTE_PLANNER_BACKEND` | `auto` | `cpp`, `python`, or `auto`; default search should use the C++ strategy planner |
| `ROUTE_TRAINING_DATA_DIR` | `backend/data/route_training` | CSV, artifact, and model directory |
| `ROUTE_DATASET_MODE` | `auto` | `auto`, `mock`, or `historical` |
| `SESSION_COOKIE_SECURE` | `false` locally | Should be `true` behind HTTPS in production |
| `VITE_AI_SEARCH_ENABLED` | `false` | Whether the frontend AI search entry is enabled |
| `AI_MODEL_PROVIDER` | `deepseek` | Agent model provider |
| `DEEPSEEK_API_KEY` | empty | DeepSeek API key |
| `AI_AGENT_TURN_MODE` | `single` | Single-call or dual-call agent mode |
| `LANGGRAPH_CHECKPOINT_DATABASE_URL` | set in compose | LangGraph PostgreSQL checkpoint storage |
| `AMAP_WEB_SERVICE_KEY` | empty | Amap Web Service key |
| `BAIDU_MAP_WEB_SERVICE_AK` | empty | Baidu Map Web Service AK |
| `AI_AGENT_POI_DUAL_VERIFY_ENABLED` | `false` | Enables Amap/Baidu dual-source POI verification |

See [backend/app/config.py](./backend/app/config.py) for the full configuration list.

## Project Structure

```text
frontend/                 React + TypeScript + Vite
backend/app/              FastAPI routers, services, schemas, agents
backend/planner/          C++17 planner and pybind11 bindings
backend/data/route_training/
database/init.sql         MySQL initialization script
description/              design and API documentation
docker-compose.yml        local orchestration
```

## Tests

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

## Data and Disclaimer

Current route strategies are based on mock data or aggregated offline CSV estimates. They do not represent realtime fares, realtime inventory, or purchasable schedules. External platform buttons are only segment-search entry points. Final prices, inventory, refund/change policies, and booking rules are controlled by the external platforms.

## License

This project is currently intended for learning, demonstration, and beta validation.
