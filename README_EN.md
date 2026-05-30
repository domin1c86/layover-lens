<p align="center">
  <h1 align="center">✈️🚄 Layover Lens（中转助手）</h1>
  <p align="center"><em>Smart Flight & Train Transfer Search Engine</em></p>
</p>

---

**Layover Lens** is a multi-modal transit search platform that finds optimal transfer routes between cities by combining flights and trains. Rather than searching each platform individually, users get a unified view of the best connections — optimized by price, duration, number of transfers, or a weighted balanced score.

## Architecture

```
┌──────────────────────────────────────────────────┐
│  Frontend  React 18 + TypeScript + Vite         │
│            Dark mode · i18n (zh/en) · motion    │
│            Port 3000                             │
├──────────────────────────────────────────────────┤
│  API       Python FastAPI                        │
│            Pydantic validation · /api/v1/*       │
│            Port 8000                             │
├──────────────────────────────────────────────────┤
│  Planner   C++17 (pybind11) ← auto-detect → Python│
│            Multi-objective graph search           │
├──────────────────────────────────────────────────┤
│  Data      MySQL 8.0 · Mock adapter ·            │
│            795 seed routes (360 flights +         │
│            435 trains) over 3 days               │
├──────────────────────────────────────────────────┤
│  AI        DeepSeek LLM · Multi-turn session     │
│            Natural language → structured search   │
└──────────────────────────────────────────────────┘
```

## Key Features

- **Multi-Objective Route Search** — Optimize for cheapest price, shortest time, fewest transfers, or a weighted balanced recommendation
- **Multi-Modal Transfers** — Mix flights and trains in a single journey (e.g., fly Beijing → Shanghai, then train to Hangzhou)
- **Rich Filtering** — Time range, max price/duration, preferred transport type, excluded cities, required transfer cities, overnight flag
- **AI-Powered Natural Language Search** — Type "Find me the fastest way from Beijing to Kunming next Tuesday" and let the AI extract structured search parameters across multiple conversation turns
- **Platform Labels** — Each leg shows its booking source (Railway 12306, Ctrip, Qunar, Fliggy)
- **Favorites** — Save and manage preferred routes with local persistence
- **Dark Mode & i18n** — Full Chinese/English support with theme-aware design tokens

## Quick Start (Docker)

```bash
git clone <repo-url> && cd layover-lens
docker compose up --build
# Frontend: http://localhost:3000    Backend API: http://localhost:8000/docs
```

The Docker setup starts three services:
- **frontend** (Nginx serving static files + API proxy)
- **backend** (FastAPI with C++ route planner)
- **mysql** (Seed data with 40 cities, 80+ stations, 795 routes)

To rebuild after making changes:
```bash
docker compose up --build          # full rebuild
docker compose restart backend     # restart single service
```

To reset the database:
```bash
docker compose down -v && docker compose up --build
```

## Local Development

### Frontend

```bash
cd frontend
npm install
npm run dev          # Vite dev server on port 3000, proxies /api → localhost:8000
npm run test         # Vitest unit tests
npm run build        # TypeScript check + production build
```

When running the backend in Docker and the frontend locally:
```bash
VITE_PROXY_TARGET=http://localhost:8000 npm run dev
```

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

For faster planning, build the C++ module:
```bash
cd backend/planner && mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build .
```

### Backend Tests

```bash
docker compose exec backend python -m pytest tests/ -v
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/search` | Multi-objective route search |
| `GET` | `/api/v1/cities` | City autocomplete by keyword |
| `POST` | `/api/v1/search/ai/sessions` | Start AI search session |
| `POST` | `/api/v1/search/ai/sessions/{id}/messages` | Send message in AI session |
| `POST` | `/api/v1/search/ai/sessions/{id}/confirm` | Confirm & execute AI search |
| `GET` | `/api/v1/search/ai/sessions/{id}` | Get AI session state |
| `POST` | `/api/v1/auth/login` | User login |
| `POST` | `/api/v1/auth/register` | User registration |
| `GET` | `/api/v1/user/profile` | Get current user profile |
| `PATCH` | `/api/v1/user/profile` | Update user profile |
| `GET` | `/api/v1/user/preferences` | Get user preferences |
| `PUT` | `/api/v1/user/preferences` | Update user preferences |
| `POST` | `/api/v1/favorites` | Save a route to favorites |
| `GET` | `/api/v1/favorites` | List saved favorites |
| `DELETE` | `/api/v1/favorites/{id}` | Remove a favorite |
| `GET` | `/health` | Service health & backend info |

Full API spec: [docs/frontend-api-specification.md](docs/frontend-api-specification.md)

## Configuration

Key environment variables (set via `docker-compose.yml` or `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_SOURCE` | `mock` | Data adapter: `mock` (MySQL + in-memory fallback) or `mysql` |
| `ROUTE_PLANNER_BACKEND` | `auto` | Planner impl: `python`, `cpp`, or `auto` |
| `DEEPSEEK_API_KEY` | — | DeepSeek API key for AI search |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | Model name for AI search |
| `DATABASE_URL` | — | MySQL connection string |
| `CORS_ORIGINS` | `["http://localhost:3000", ...]` | Allowed CORS origins |
| `MAX_ROUTES` | `8` | Max results per search |
| `DEFAULT_MAX_TRANSFERS` | `2` | Max transfers per route |

See [backend/app/config.py](backend/app/config.py) for all available settings.

## Project Structure

```
layover-lens/
├── frontend/            React 18 + TypeScript + Vite
│   ├── src/
│   │   ├── components/  SearchTab, AiSearchTab, FavoritesTab, SettingsModal, TopNav, Footer
│   │   ├── context/     ThemeContext, LocaleContext, FavoritesContext
│   │   ├── locales/     zh/en translation dictionary
│   │   ├── services/    Axios API client
│   │   ├── styles/      Design tokens, reset, dark mode overrides
│   │   └── types/       TypeScript interfaces mirroring backend schemas
│   └── nginx.conf       Production static serving + API proxy
├── backend/             Python FastAPI
│   ├── app/
│   │   ├── routers/     Search, cities, auth, user, bookings
│   │   ├── services/    Search engine, AI agent, route planner
│   │   ├── data_source/ Pluggable adapters (MySQL, in-memory)
│   │   ├── config.py    pydantic-settings configuration
│   │   └── schemas.py   API request/response models
│   ├── planner/         C++17 route planner (pybind11)
│   └── tests/
├── database/            MySQL schema + seed data
├── docs/                Documentation
└── docker-compose.yml   3-service orchestration
```

## Tech Stack

**Frontend:** React 18 · TypeScript · Vite · motion (framer-motion) · Axios · Vitest  
**Backend:** Python · FastAPI · Pydantic · MySQL Connector · DeepSeek API · pybind11  
**Database:** MySQL 8.0 · 40 cities · 80+ stations · 795 seed routes  
**Infrastructure:** Docker Compose · Nginx · CMake (C++ planner)

## License

This project is for demonstration purposes.
