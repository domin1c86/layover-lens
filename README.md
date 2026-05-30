# Layover Lens

Layover Lens is a multi-modal transit assistant for searching flight and train transfer routes between cities.

## Run With Docker

The recommended way to run the project is Docker Compose. It packages the frontend, backend, and MySQL database so the app can start on any machine with Docker installed.

```bash
docker compose up --build
```

After startup:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

## Services

- `frontend`: React app built by Vite and served by Nginx
- `backend`: FastAPI application with route planning logic
- `mysql`: MySQL 8 with seeded mock transit data from `database/init.sql`

## Local Backend Test

The backend test suite passes under the Python 3.9.6 environment:

```powershell
   .\layover-lens\backend\.venv39\Scripts\python.exe' -m pytest tests -v
```
