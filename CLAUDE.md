# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Layover Lens (中转助手)** is a multi-modal transit assistant for searching flight and train transfer routes between cities. It supports optimizing for price, time, transfer count, or balanced scoring, with both standard form-based search and AI-powered natural language search.

## Architecture

### Modular Monolith Design

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React 18 + TypeScript + Vite)                    │
│  - Tab-based UI: SearchTab, AiSearchTab, FavoritesTab       │
│  - Dark mode via ThemeContext (localStorage + data-theme)   │
│  - i18n via LocaleContext (zh/en flat dict + interpolation) │
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

1. **Dual Planner Backend**: `ROUTE_PLANNER_BACKEND=auto` (default, auto-detects C++ at startup) or `python`/`cpp` to force a specific backend. The Docker Compose config overrides default to `cpp`. The C++ module (`route_planner`) is a pybind11 binding loaded from `backend/planner/build/`. It exposes `PathPlanner`, `TransportType`, and `OptimizeTarget` to Python.
2. **Pluggable Data Sources**: `DATA_SOURCE=mock|mysql`. The `mock` adapter uses `MySQLCatalogRepository` as primary with `InMemoryCatalogRepository` as fallback — this is the default in Docker Compose. `DATA_SOURCE=mock` does **not** mean pure in-memory; it means MySQL-first with fallback.
3. **Multi-objective Optimization**: Price, time, transfer count, or weighted balanced scoring (0.4 price + 0.35 time + 0.25 transfer).
4. **Rich Filtering**: Time ranges, transfer city constraints, transport type preferences, price/duration limits, overnight allowance.
5. **AI Search is Session-Based Multi-Turn**: Not a single-shot endpoint. The AI assistant collects missing fields across chat turns via DeepSeek API, then executes search on user confirmation. The DeepSeek system prompt is hardcoded in Chinese in `backend/app/services/ai_agent.py` and requires JSON output with fields: `assistant_message`, `extracted_request`, `should_confirm`, `summary`.
6. **Transfer Timing Constraints**: The planner enforces minimum transfer times: 45 min same-station, 90 min same-city different stations, 480 min max layover, 1440 min (24h) max total duration. These are configurable via env vars (see Configuration).
7. **Tests Run During Docker Build**: `backend/Dockerfile` runs `pytest tests -v` before completing the image build. Test failures block the Docker build.
8. **Backend Config**: `backend/app/config.py` uses pydantic-settings with `.env` file support. The `Settings` object and dependent singletons (`get_settings`, `create_data_source`, `get_search_service`) are cached via `functools.lru_cache`. Tests use `_fresh_client()` to reset these caches between cases.

### Frontend Architecture

**No client-side router.** Tab switching is state-driven via `useState<'search' | 'ai' | 'favorites'>` in `HomePage.tsx`. There is no React Router or any SPA routing library.

**Component tree:**
```
<App>
  <LocaleProvider>
    <ThemeProvider>
      <HomePage>
        <TopNav />          — tabs + theme/lang/account dropdowns (framer-motion animated)
        <SearchBar />       — city pickers, date, optimize, advanced filters drawer
        {SearchTab | AiSearchTab | FavoritesTab}
        <Footer />
      </HomePage>
      <SettingsModal />     — overlay modal, rendered at root level
    </ThemeProvider>
  </LocaleProvider>
</App>
```

**State management:** React built-in hooks only — no Redux, Zustand, or other external state library. Favorites are persisted to `localStorage` via a standalone `useFavorites()` hook. AI chat state lives in `AiSearchTab`.

**Styling:** Plain CSS files with BEM-like naming (`.settings-modal__header`, `.search-bar--compact`). CSS custom properties on `:root` define design tokens; dark mode swaps them via `html[data-theme="dark"]`. No Tailwind, CSS Modules, or CSS-in-JS. All theme tokens are in `frontend/src/styles/theme.css`.

**Animation:** Uses the `motion` package (rebranded framer-motion v12+) for `AnimatePresence`, `motion.div` transitions in SettingsModal overlay/dialog and TopNav dropdowns.

**Path aliases:** `@/*` maps to `src/*` (configured in `tsconfig.json`).

**i18n:** All UI text in `frontend/src/locales/index.ts` — a flat dictionary with `zh` and `en` keys, ~184 leaf keys per language. The `useLocale()` hook provides `t(key, vars?)` with dot-path lookup and `{{var}}` interpolation. Falls back to `zh` value if key missing in current language, then to raw key. Both dictionaries have identical key structure.

**SettingsModal:** A recent major feature (`frontend/src/components/SettingsModal/`) with 6 panels: Account, Security, Appearance, AIHistory, Import, Devices. Uses a `PANELS` record mapping tab names to components. Security panel contains a child `ForgotPasswordModal` with a 4-step wizard (email → verify → reset → success) using mock local state. All panels are locale-aware and currently mock/local-state only (no backend persistence).

**Frontend test coverage is minimal:** Only `LocaleContext.test.tsx` and `locales/index.test.ts` exist. Test framework is Vitest + jsdom + Testing Library.

### Backend Thread Safety

- `SearchService._ai_sessions` dict is protected by a `threading.Lock` — all session CRUD operations acquire it.
- `MockAdapter` uses double-check locking for lazy catalog loading from MySQL.

### Unused / Planned Code

- `backend/app/services/query_parser.py` — `RuleBasedQueryParser` for natural language search without AI. Fully implemented but **not wired to any endpoint**. Likely intended for a future non-AI natural language search route.

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

# If backend is running in Docker but frontend is local:
VITE_PROXY_TARGET=http://localhost:8000 npm run dev

# Production build (runs tsc type-check then vite build)
npm run build

# Preview production build
npm run preview

# Run frontend tests (Vitest + jsdom + Testing Library)
npm run test

# Watch mode
npm run test:watch
```

For local development without Docker, start the backend separately and the Vite dev server will proxy API requests.

In Docker (production build), the frontend is served by **Nginx** (not Vite). Nginx serves static files on port 3000 and proxies `/api/` requests to `backend:8000` (see `frontend/nginx.conf`). This means `docker compose up --build` is closer to production behavior than `npm run dev`.

There is **no linter or formatter** configured (no ESLint, no Prettier). The `build` script runs `tsc` for type-checking before the Vite build — this is the only static analysis step.

### Running Backend Locally

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend needs MySQL running. For quick iteration on search logic, use `DATA_SOURCE=mock` which uses in-memory data.

### Backend Testing

```bash
# Run all tests inside container
docker compose exec backend python -m pytest tests/ -v

# Run specific test
docker compose exec backend python -m pytest tests/test_search.py::test_search_endpoint_returns_ranked_routes -v

# Run with local Python 3.9 (as documented in README)
.\.venv39\Scripts\python.exe -m pytest tests -v
```

All 12 tests are in a single file (`tests/test_search.py`). Three patterns are used:
- **Standard API tests** — direct `TestClient` calls against the real app
- **Legacy alias tests** — verify old field names (`date`, `optimize`, `filters.max_transfer`) still work
- **AI multi-turn tests** — mock `DeepSeekChatClient.respond` via `monkeypatch.setattr` to simulate multi-turn conversation flows

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

## Frontend i18n

All UI text lives in `frontend/src/locales/index.ts` as a flat dictionary with `zh` and `en` keys. The `useLocale()` hook (from `frontend/src/context/LocaleContext.tsx`) provides:

- `lang: 'zh' | 'en'` — current language
- `setLang(lang)` — persists to `localStorage` as `locale`
- `t(key, vars?)` — looks up by dot path (e.g., `t('settings.security.email')`) with optional `{{var}}` interpolation

When adding new user-facing strings, add them to **both** `zh` and `en` sections of the dictionary. The hook falls back to the `zh` value if a key is missing in the current language.

## Project Structure

Key files for understanding the architecture:

- `backend/app/config.py` - pydantic-settings configuration with env var mapping
- `backend/app/schemas.py` - API request/response Pydantic models with validation aliases for legacy fields
- `backend/app/services/route_planner.py` - Python planner (`PythonRoutePlanner`) + `PlanningConstraints` logic, plus `CppRoutePlanner` wrapper
- `backend/app/services/search_service.py` - Service layer orchestrating data source, planner, and AI session management
- `backend/app/services/ai_agent.py` - DeepSeek chat client with JSON-mode system prompts
- `backend/app/services/query_parser.py` - Rule-based NL query parser (implemented but not wired to any endpoint)
- `backend/app/data_source/` - Data source abstraction (`base.py`), factory (`factory.py`), and adapters
- `backend/planner/` - C++ planner source (`planner.cpp`, `bindings.cpp`, `CMakeLists.txt`)
- `frontend/src/types/index.ts` - TypeScript type definitions mirroring backend schemas
- `frontend/src/services/api.ts` - Axios API client (no interceptors, no retry logic)
- `frontend/src/context/ThemeContext.tsx` - Dark mode provider (toggles `data-theme="dark"` on `<html>`)
- `frontend/src/context/LocaleContext.tsx` - i18n provider
- `frontend/src/locales/index.ts` - Translation dictionary (~184 keys per language)
- `frontend/src/styles/theme.css` - Design tokens (CSS custom properties), reset, dark mode overrides
- `frontend/src/components/SettingsModal/` - Settings modal with NavMenu + 6 panels + ForgotPassword flow
- `frontend/src/test/setup.ts` - Vitest setup (imports `@testing-library/jest-dom`)
- `database/init.sql` - Schema + 3 days of seed data (2026-04-22 to 2026-04-24)

## Configuration

Environment variables (set in `docker-compose.yml` or `.env`):
- `DATA_SOURCE=mock|mysql` - Data source type
- `ROUTE_PLANNER_BACKEND=python|cpp|auto` - Planner implementation (default: `auto`)
- `DATABASE_URL` - MySQL connection string
- `CORS_ORIGINS` - JSON list of allowed origins (default: `["http://localhost:3000", "http://127.0.0.1:3000"]`)
- `APP_NAME` / `APP_VERSION` - FastAPI metadata (default: `"Layover Lens API"` / `"1.0.0"`)
- `API_V1_PREFIX` - API prefix (default: `"/api/v1"`)
- `MAX_ROUTES` - Default: 8
- `DEFAULT_MAX_TRANSFERS` - Default: 2
- `MIN_TRANSFER_MINUTES_SAME_STATION` - Default: 45
- `MIN_TRANSFER_MINUTES_SAME_CITY` - Default: 90
- `MAX_LAYOVER_MINUTES` - Default: 480
- `MAX_TOTAL_DURATION_MINUTES` - Default: 1440 (24h)
- `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` / `DEEPSEEK_TIMEOUT_SECONDS` - AI search configuration
- `AI_SEARCH_MAX_HISTORY_MESSAGES` - Default: 12

Note: `allow_overnight` defaults to `true` in the `SearchRequest` schema — overnight transfers are permitted unless explicitly disabled.
