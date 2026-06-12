<p align="right">
  <a href="./README.md">中文</a> | English
</p>

<p align="center">
  <h1 align="center">Layover Lens</h1>
  <p align="center"><em>A multimodal route strategy recommendation system for intercity travel in China</em></p>
</p>

---

Layover Lens is an open-source project for validating city-level transportation strategy recommendations. The current version does not promise realtime fares, realtime inventory, or purchasable schedules. Instead, it returns route strategies such as `Beijing -> Nanjing -> Chengdu`, with estimated cost, estimated duration, service density, confidence, and external ticket-search entry points for each segment.

## Current Status

- **Route strategy recommendations**: default search returns city-path strategies instead of detailed train or flight schedules.
- **C++ algorithm core**: traffic graph construction, candidate retrieval, segment estimation, direct-price guardrails, and linear ranking run in C++17 through pybind11.
- **Simple linear model**: the current model artifact is `linear_ranker_v1.json`; it controls C++ ranking weights and does not yet update online from user feedback.
- **Mock / historical data modes**: mock data is used when no training artifact is available; historical CSV/XLSX artifacts can drive graph features and model weights.
- **AI conversational search**: a LangGraph-based agent collects fields such as origin, destination, and date, then executes strategy search after user confirmation.
- **Agent tools**: date, weather, and real POI tools. POI search uses Amap first and Baidu as fallback, with a lightweight RAG cache.
- **Account security**: real backend registration and login, HttpOnly cookie sessions, CSRF, device management, TOTP 2FA, and optional 2FA replacement for email verification codes.
- **Frontend experience**: regular search, AI search, favorites, local avatars, theme switching, Chinese/English UI, route feedback, and external ticket-link warnings.
- **Feedback-loop foundation**: route feedback can be submitted anonymously or by logged-in users and stored in MySQL for later annotation and training export.

## Architecture

```text
React 18 + TypeScript + Vite frontend (:3000)
  -> Axios API client
  -> Nginx / Vite proxy for /api

FastAPI backend (:8000)
  -> auth / user / cities / search routers
  -> SearchService calls the C++ route strategy planner
  -> LangGraph Agent + tools + checkpoint storage

C++ planner module
  -> TrafficGraphBuilder
  -> CandidateRetriever
  -> RankingModel
  -> pybind11 bindings

MySQL 8.0
  -> users, sessions, devices, preferences, favorites
  -> mock catalog, POI cache, route feedback, training metadata

PostgreSQL
  -> LangGraph checkpoint storage
```

## Quick Start

```powershell
git clone <repo-url>
cd layover-lens
docker compose up --build -d backend frontend
```

URLs:

- Frontend: `http://localhost:3000`
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

Local backend development uses the Python 3.10.11 `.venv310` virtual environment:

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

All user-facing frontend text should live in `frontend/src/locales`, with mirrored Chinese and English keys.

## Route Training Data and Model

Training data lives under:

```text
backend/data/route_training/
  raw_csv/       # raw CSV/XLSX files, ignored by Git by default
  artifacts/     # aggregated traffic graph artifacts
  models/        # linear ranker weight files
```

The online search needs both artifacts:

- `backend/data/route_training/artifacts/route_edges_v1.json.gz`
- `backend/data/route_training/models/linear_ranker_v1.json`

Build and inspect:

```powershell
cd backend
.\.venv310\Scripts\python.exe -m app.cli.route_training init
.\.venv310\Scripts\python.exe -m app.cli.route_training status
.\.venv310\Scripts\python.exe -m app.cli.route_training build
.\.venv310\Scripts\python.exe -m app.cli.route_training validate
.\.venv310\Scripts\python.exe -m app.cli.route_training evaluate
```

With `ROUTE_DATASET_MODE=auto`, the service uses a historical artifact when available and falls back to mock when it is missing. You can also force:

- `ROUTE_DATASET_MODE=mock`
- `ROUTE_DATASET_MODE=historical`

Generated training artifacts are ignored by `.gitignore` by default. You can add the required raw data to the `raw_csv` directory yourself if needed.

## Feedback and Self-Improvement Boundary

The project can already collect route feedback:

- Route-card feedback from regular search.
- AI-search experience feedback.
- Anonymous and logged-in feedback.
- Four star ratings, text comments, adopted route selections, clicked provider, search request snapshot, and recommendation snapshot.
- `dataset_version` and `model_version` are stored for model-performance tracing.

The project does not yet update online model parameters directly from user feedback. The future training loop is:

```text
route_feedback / route_feedback_annotations
  -> clean valid samples
  -> generate manual or rule-based labels
  -> train a candidate model offline
  -> compare with evaluate
  -> manually approve and publish
```

Small feedback sets are noisy and should not automatically change production weights. The current first version keeps offline-trained, offline-evaluated, manually published, and rollback-friendly.

## API List

Full API documentation: [description/api-interface-list.md](./description/api-interface-list.md).

Common endpoints:

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Service, data source, planner, AI, POI, and training artifact summary |
| `GET` | `/api/v1/cities` | City list and keyword filtering |
| `POST` | `/api/v1/search` | Route strategy search |
| `POST` | `/api/v1/search/feedback` | Route feedback, supports anonymous submission |
| `GET` | `/api/v1/search/feedback/annotated` | Export annotated feedback samples |
| `POST` | `/api/v1/search/ai/sessions/stream` | Create an AI session and stream response |
| `POST` | `/api/v1/search/ai/sessions/{session_id}/confirm/stream` | Confirm AI search and stream results |
| `GET` | `/api/v1/search/ai/memory` | Read Agent long-term memory |
| `DELETE` | `/api/v1/search/ai/memory/{memory_key}` | Delete one Agent memory item |
| `POST` | `/api/v1/auth/register` | Register and set session cookies |
| `POST` | `/api/v1/auth/login` | Login, may return a TOTP challenge |
| `POST` | `/api/v1/auth/logout` | Logout |
| `GET` | `/api/v1/user/profile` | Current user profile |
| `PUT` | `/api/v1/user/profile` | Update user profile |
| `GET` | `/api/v1/user/devices` | Login device list |
| `POST` | `/api/v1/user/totp/setup` | Create TOTP setup data |
| `POST` | `/api/v1/user/totp/enable` | Enable TOTP |
| `POST` | `/api/v1/user/totp/disable` | Disable TOTP |

## Key Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `APP_ENV` | `development` | `development` or `production` |
| `DATABASE_URL` | set in compose | MySQL connection string |
| `ROUTE_PLANNER_BACKEND` | `auto` | `cpp`, `python`, or `auto` |
| `ROUTE_TRAINING_DATA_DIR` | `backend/data/route_training` | CSV, artifact, and model directory |
| `ROUTE_DATASET_MODE` | `auto` | `auto`, `mock`, or `historical` |
| `SESSION_COOKIE_SECURE` | `false` locally | Should be `true` behind HTTPS in production |
| `CSRF_SECRET` | dev default | Must be replaced in production |
| `TOTP_ENCRYPTION_SECRET` | dev default | Must be replaced in production |
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
frontend/                         React + TypeScript + Vite
backend/app/                      FastAPI routers, services, schemas, agents
backend/planner/                  C++17 planner and pybind11 bindings
backend/data/route_training/      training data, artifacts, model weights
database/init.sql                 MySQL initialization script
description/                      design and API documentation
docker-compose.yml                local orchestration
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

Current route strategies are based on mock data or aggregated offline CSV/XLSX estimates. They do not represent realtime fares, realtime inventory, or purchasable schedules. External platform buttons are only segment-search entry points. Final prices, inventory, refund/change policies, and booking rules are controlled by the external platforms.

## License

This project is currently intended for learning, demonstration, and beta validation.
