# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Layover Lens (中转助手)** is a multi-modal transit assistant for searching flight and train transfer routes between cities. It supports optimizing for price, time, transfer count, or balanced scoring, with both standard form-based search and AI-powered natural language search.

## Architecture

### Modular Monolith Design

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React + TypeScript + Vite)                       │
│  - Tab-based UI: SearchTab, AiSearchTab, FavoritesTab       │
│  - Dark mode via ThemeContext (localStorage + CSS vars)     │
│  - Port: 3000                                               │
├─────────────────────────────────────────────────────────────┤
│  API Gateway (Python FastAPI)                               │
│  - Routes: /api/v1/search, /api/v1/search/ai/sessions,      │
│            /api/v1/cities                                   │
│  - Port: 8000                                               │
├─────────────────────────────────────────────────────────────┤
│  Core Modules                                               │
│  ├─ Path Planner (Python + Optional C++17 via pybind11)    │
│  │   Multi-objective graph algorithm with filtering         │
│  ├─ Data Source (Pluggable: Mock → MySQL → Scraper/API)    │
│  └─ AI Assistant (DeepSeek LLM, multi-turn session-based)  │
├─────────────────────────────────────────────────────────────┤
│  MySQL 8.0 - Cities, stations, routes with 3-day schedule  │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Dual Planner Backend**: `ROUTE_PLANNER_BACKEND=auto` (default, auto-detects C++ at startup) or `python`/`cpp` to force a specific backend. The Docker Compose config overrides default to `cpp`. The C++ module (`route_planner`) is a pybind11 binding loaded from `backend/planner/build/`.
2. **Pluggable Data Sources**: `DATA_SOURCE=mock|mysql`. The `mock` adapter actually uses `MySQLCatalogRepository` as primary with `InMemoryCatalogRepository` as fallback — this is the default in Docker Compose.
3. **Multi-objective Optimization**: Price, time, transfer count, or weighted balanced scoring (0.4 price + 0.35 time + 0.25 transfer).
4. **Rich Filtering**: Time ranges, transfer city constraints, transport type preferences, price/duration limits, overnight allowance.
5. **AI Search is Session-Based Multi-Turn**: Not a single-shot endpoint. The AI assistant collects missing fields across chat turns via DeepSeek API, then executes search on user confirmation.
6. **Transfer Timing Constraints**: The planner enforces minimum transfer times: 45 min same-station, 90 min same-city different stations, 480 min max layover, 1440 min (24h) max total duration. These are configurable via env vars (see Configuration).
7. **Tests Run During Docker Build**: `backend/Dockerfile` runs `pytest tests -v` before completing the image build. Test failures block the Docker build.

## Common Commands

### Development (Docker Compose)

```bash
# Start all services (builds if needed)
docker compose up --build

# View logs
docker compose logs -f [frontend|backend|mysql]

# Restart specific service
docker compose restart backend

# Clean restart with fresh database
docker compose down -v && docker compose up --build
```

### Frontend Development

```bash
cd frontend

# Local dev server (Vite proxies /api to localhost:8000)
npm run dev

# Production build
npm run build

# Preview production build
npm run preview
```

For local development without Docker, start the backend separately and the Vite dev server will proxy API requests.

### Running Backend Locally

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend needs MySQL running. For quick iteration on search logic, use `DATA_SOURCE=mock` which uses in-memory data.

In Docker (production build), the frontend is served by **Nginx** (not Vite). Nginx serves static files on port 3000 and proxies `/api/` requests to `backend:8000` (see `frontend/nginx.conf`). This means `docker compose up --build` is closer to production behavior than `npm run dev`.

### Backend Testing

```bash
# Run all tests inside container
docker compose exec backend python -m pytest tests/ -v

# Run specific test
docker compose exec backend python -m pytest tests/test_search.py::test_search_endpoint_returns_ranked_routes -v

# Run with local Python 3.9 (as documented in README)
.\.venv39\Scripts\python.exe -m pytest tests -v
```

Tests use `_fresh_client()` to reset `lru_cache`-backed service and data source singletons between test cases.

### C++ Planner Build

The Dockerfile builds the C++ module during image creation:

```bash
cmake -S planner -B planner/build -DCMAKE_BUILD_TYPE=Release
cmake --build planner/build --config Release
```

For manual build inside the backend container:

```bash
cd backend/planner
mkdir -p build && cd build
cmake ..
make

# Verify import
python -c "import route_planner; print('C++ module loaded')"
```

The module path is added to `sys.path` at runtime from `backend/planner/build/`.

### Database

```bash
# Connect to MySQL
docker compose exec mysql mysql -uroot -pdevpassword layover_lens

# Check seed data loaded
SELECT COUNT(*) FROM routes;  -- Expected: 795 (265 routes x 3 days)
```

## API Endpoints

- `POST /api/v1/search` - Main search with filters (see `test_search.py` for examples)
- `GET /api/v1/cities?keyword=北京` - City search
- `GET /health` - Health check showing `data_source`, `planner_backend`, and `ai_search_backend`

### AI Search (Multi-Turn Session API)

- `POST /api/v1/search/ai/sessions` - Create session with opening message
- `POST /api/v1/search/ai/sessions/{session_id}/messages` - Append user message
- `POST /api/v1/search/ai/sessions/{session_id}/confirm` - Confirm (`{"confirmed": true}`) to execute search, or reject to continue refining
- `GET /api/v1/search/ai/sessions/{session_id}` - Get current session state

The AI search flow: `COLLECTING` → `AWAITING_CONFIRMATION` → `COMPLETED`. See `test_search.py::test_ai_search_collects_fields_across_turns_and_executes_on_confirm` for a full walkthrough.

## Project Structure

Key files for understanding the architecture:

- `backend/app/schemas.py` - API request/response Pydantic models with validation aliases for legacy fields
- `backend/app/services/route_planner.py` - Python planner (`PythonRoutePlanner`) + `PlanningConstraints` logic, plus `CppRoutePlanner` wrapper
- `backend/app/services/search_service.py` - Service layer orchestrating data source, planner, and AI session management
- `backend/app/services/ai_agent.py` - DeepSeek chat client with JSON-mode system prompts
- `backend/app/data_source/` - Data source abstraction (`base.py`), factory (`factory.py`), and adapters
- `backend/planner/` - C++ planner source (`planner.cpp`, `bindings.cpp`, `CMakeLists.txt`)
- `frontend/src/types/index.ts` - TypeScript type definitions mirroring backend schemas
- `frontend/src/services/api.ts` - Axios API client
- `frontend/src/context/ThemeContext.tsx` - Dark mode provider
- `database/init.sql` - Schema + 3 days of seed data (2026-04-22 to 2026-04-24)

## Configuration

Environment variables (set in `docker-compose.yml` or `.env`):
- `DATA_SOURCE=mock|mysql` - Data source type
- `ROUTE_PLANNER_BACKEND=python|cpp` - Planner implementation
- `DATABASE_URL` - MySQL connection string
- `MAX_ROUTES` - Default: 8
- `DEFAULT_MAX_TRANSFERS` - Default: 2
- `MIN_TRANSFER_MINUTES_SAME_STATION` - Default: 45
- `MIN_TRANSFER_MINUTES_SAME_CITY` - Default: 90
- `MAX_LAYOVER_MINUTES` - Default: 480
- `MAX_TOTAL_DURATION_MINUTES` - Default: 1440 (24h)
- `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` / `DEEPSEEK_TIMEOUT_SECONDS` - AI search configuration
