# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Layover Lens (中转助手)** is a transit assistance tool that helps travelers find optimal transfer routes between cities using flights and trains. It supports multi-modal transportation search with customizable optimization criteria (price, time, transfers, or balanced).

**Current Status**: Design phase completed, implementation not started. See `plan.md` for detailed execution steps.

## Architecture

### Modular Monolith Design

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React + TypeScript)                              │
│  - Simple/Advanced/AI search modes                          │
│  - Card-based results with timeline visualization           │
│  - Port: 3000                                               │
├─────────────────────────────────────────────────────────────┤
│  API Gateway (Python FastAPI)                               │
│  - Routes: /api/v1/search, /api/v1/cities                   │
│  - Port: 8000                                               │
├─────────────────────────────────────────────────────────────┤
│  Core Modules                                               │
│  ├─ Path Planner (C++17 + pybind11)                        │
│  │   Multi-objective graph algorithm (Dijkstra/A*)         │
│  ├─ Data Source (Python)                                    │
│  │   Pluggable: Mock → Scraper → API                       │
│  └─ AI Assistant (Python)                                   │
│      Natural language search guidance                      │
├─────────────────────────────────────────────────────────────┤
│  MySQL 8.0 - Cities, stations, routes, schedules           │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **C++ Path Planner**: Performance-critical routing engine exposed to Python via pybind11
2. **Pluggable Data Sources**: Abstract `DataSourceBase` allows swapping implementations without changing business logic
3. **Multi-objective Optimization**: Supports optimizing for price, time, transfer count, or weighted combination

## Common Commands

### Development Environment (Docker Compose)

```bash
# Start all services (frontend, backend, mysql)
docker-compose up -d

# View logs
docker-compose logs -f [frontend|backend|mysql]

# Stop all services
docker-compose down

# Clean restart (removes data volumes)
docker-compose down -v && docker-compose up --build -d
```

### Frontend (React + Vite)

```bash
# Enter frontend container
docker-compose exec frontend sh

# Install dependencies (if package.json changes)
npm install

# Run dev server (already running via docker-compose)
npm run dev

# Build for production
npm run build
```

### Backend (FastAPI)

```bash
# Enter backend container
docker-compose exec backend bash

# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_search.py::test_search_endpoint -v

# API documentation (available when running)
# http://localhost:8000/docs (Swagger)
# http://localhost:8000/redoc (ReDoc)
```

### C++ Path Planner

```bash
# Build the C++ module (inside backend container)
cd planner
mkdir -p build && cd build
cmake ..
make

# The compiled .so file should be importable from Python
python -c "import route_planner; print('OK')"
```

### Database

```bash
# Connect to MySQL (inside mysql container)
docker-compose exec mysql mysql -uroot -pdevpassword layover_lens

# Re-initialize database (warning: destroys data)
docker-compose down -v
docker-compose up -d mysql
```

## Project Structure

```
├── docker-compose.yml          # Development orchestration
├── plan.md                     # Detailed implementation plan
├── frontend/                   # React + TypeScript
│   ├── src/
│   │   ├── components/         # SearchForm, ResultCards, Timeline
│   │   ├── pages/              # HomePage
│   │   ├── services/           # API clients
│   │   └── types/              # TypeScript definitions
│   └── package.json
├── backend/                    # Python FastAPI
│   ├── app/
│   │   ├── main.py             # FastAPI entry point
│   │   ├── routers/            # API route handlers
│   │   └── data_source/        # Data adapters (mock/scraper/api)
│   ├── planner/                # C++ path planning module
│   │   ├── planner.h/cpp       # Core algorithm
│   │   ├── bindings.cpp        # pybind11 bindings
│   │   └── CMakeLists.txt
│   └── tests/
├── database/
│   └── init.sql                # Schema + mock data
└── docs/superpowers/
    ├── specs/                  # Design specification
    └── plans/                  # Detailed implementation plan
```

## Key Technologies

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 18 + TypeScript 5 | UI components |
| Build | Vite 5 | Dev server & bundling |
| Backend | FastAPI 0.109 | REST API |
| Database | MySQL 8.0 | Data persistence |
| Algorithm | C++17 | Path planning performance |
| Binding | pybind11 2.11 | C++ ↔ Python interop |
| Testing | pytest | Backend tests |

## Testing Strategy

- **Backend**: pytest with FastAPI TestClient
- **Manual**: HTTP test file at `frontend/test-search.http`
- **API Docs**: Auto-generated Swagger at `/docs`

## Documentation

- **Execution Plan**: `plan.md` - Step-by-step implementation guide
- **Design Spec**: `docs/superpowers/specs/2026-04-09-layover-lens-design.md`
- **Detailed Plan**: `docs/superpowers/plans/2026-04-09-layover-lens-mvp.md`

## Implementation Notes

1. **Not Yet Implemented**: This project is in the planning phase. All code structure above represents the planned architecture.
2. **Start Implementation**: Follow `plan.md` starting from "阶段一：环境搭建"
3. **Multi-language Build**: Backend Docker image includes gcc/g++/cmake for compiling the C++ planner module
4. **Data Source Strategy**: Start with MockAdapter, migrate to ScraperAdapter, then ApiAdapter as the project matures
