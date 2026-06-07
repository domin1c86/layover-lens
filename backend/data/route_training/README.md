# Route Training Data

Place historical ticket CSV files in `raw_csv/`, then build compact artifacts with:

```powershell
cd backend
.\.venv310\Scripts\python.exe -m app.cli.route_training build
```

Generated artifacts and model files are ignored by Git. The online service loads compact artifacts from `artifacts/` and linear ranking weights from `models/`.
