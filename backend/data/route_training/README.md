# Route Training Data

This directory stores offline data for the route strategy engine.

```text
raw_csv/       # raw CSV/XLSX inputs, ignored by Git by default
artifacts/     # compact traffic graph artifacts used online
models/        # linear ranker model weights used by the C++ planner
```

Current online search needs both generated files:

- `artifacts/route_edges_v1.json.gz`
- `models/linear_ranker_v1.json`

Build and inspect:

```powershell
cd backend
.\.venv310\Scripts\python.exe -m app.cli.route_training init
.\.venv310\Scripts\python.exe -m app.cli.route_training status
.\.venv310\Scripts\python.exe -m app.cli.route_training build
.\.venv310\Scripts\python.exe -m app.cli.route_training validate
.\.venv310\Scripts\python.exe -m app.cli.route_training evaluate
```

`ROUTE_DATASET_MODE=auto` uses a historical artifact when one is available and falls back to mock data when it is missing. Set `ROUTE_DATASET_MODE=historical` to require historical data.

Generated artifacts and model files are ignored by Git by default. For an open-source release, it is reasonable to commit the compact artifact and model if they stay small enough, but do not commit raw CSV/XLSX source files.
