# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Layover Lens (中转助手)** is a multi-modal transit assistant for searching flight and train transfer routes between cities. It supports optimizing for price, time, transfer count, or balanced scoring, with both standard form-based search and AI-powered natural language search.

## Architecture

### Modular Monolith Design

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React + TypeScript + Vite)                       │
│  - Simple search mode with city/date/optimization inputs    │
│  - Card-based results with timeline visualization           │
│  - Port: 3000                                               │
├─────────────────────────────────────────────────────────────┤
│  API Gateway (Python FastAPI)                               │
│  - Routes: /api/v1/search, /api/v1/search/ai, /api/v1/cities│
│  - Port: 8000                                               │
├─────────────────────────────────────────────────────────────┤
│  Core Modules                                               │
│  ├─ Path Planner (Python + Optional C++17 via pybind11)    │
│  │   Multi-objective graph algorithm with filtering         │
│  ├─ Data Source (Pluggable: Mock → MySQL → Scraper/API)    │
│  └─ AI Assistant (LLM-based natural language parsing)      │
├─────────────────────────────────────────────────────────────┤
│  MySQL 8.0 - Cities, stations, routes with 3-day schedule  │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Dual Planner Backend**: `ROUTE_PLANNER_BACKEND=python` (default) or `cpp` (C++17 via pybind11 for performance)
2. **Pluggable Data Sources**: `DATA_SOURCE=mock|mysql` - swap via environment variable without code changes
3. **Multi-objective Optimization**: Price, time, transfer count, or weighted balanced scoring
4. **Rich Filtering**: Time ranges, transfer city constraints, transport type preferences, price/duration limits

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

### Backend Testing

```bash
# Run all tests inside container
docker compose exec backend python -m pytest tests/ -v

# Run specific test
docker compose exec backend python -m pytest tests/test_search.py::test_search_endpoint_returns_ranked_routes -v

# Run with local Python 3.9 (as documented in README)
.\.venv39\Scripts\python.exe -m pytest tests -v
```

### C++ Planner Build

```bash
# Inside backend container
cd planner
mkdir -p build && cd build
cmake ..
make

# Verify import
python -c "import route_planner; print('C++ module loaded')"
```

### Database

```bash
# Connect to MySQL
docker compose exec mysql mysql -uroot -pdevpassword layover_lens

# Check seed data loaded
SELECT COUNT(*) FROM routes;  -- Expected: 795 (265 routes x 3 days)
```

## API Endpoints

- `POST /api/v1/search` - Main search with filters (see `test_search.py` for examples)
- `POST /api/v1/search/ai` - Natural language search (`query: "北京到上海明天最便宜"`)
- `GET /api/v1/cities?keyword=北京` - City search
- `GET /health` - Health check showing data_source and planner_backend

See `backend/tests/test_search.py` for comprehensive usage examples of all filters.

## Project Structure

Key files for understanding the architecture:

- `backend/app/schemas.py` - API request/response models with validation
- `backend/app/services/route_planner.py` - Python planner + PlanningConstraints logic
- `backend/app/services/search_service.py` - Service layer, data source integration
- `backend/app/data_source/` - Data source abstraction and implementations
- `backend/planner/` - C++ planner source (planner.cpp, bindings.cpp)
- `frontend/src/types/index.ts` - TypeScript type definitions
- `database/init.sql` - Schema + 3 days of seed data (2026-04-22 to 2026-04-24)

## Configuration

Environment variables (set in docker-compose.yml or .env):
- `DATA_SOURCE=mock|mysql` - Data source type
- `ROUTE_PLANNER_BACKEND=python|cpp` - Planner implementation
- `DATABASE_URL` - MySQL connection string
- `MAX_ROUTES` - Default: 8
- `DEFAULT_MAX_TRANSFERS` - Default: 2
