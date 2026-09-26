# Web App Runbook

## Start ETL

```powershell
cd "C:\Users\m.ortega\Documents\M.ORTEGA\m.ortega\fin per\DWH"
uv run python src/main.py
```

## Start Backend

```powershell
cd "C:\Users\m.ortega\Documents\M.ORTEGA\m.ortega\fin per\DWH\app\backend"
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Start Frontend

```powershell
cd "C:\Users\m.ortega\Documents\M.ORTEGA\m.ortega\fin per\DWH\app\frontend"
npm install
npm run dev
```

Open `http://127.0.0.1:3000`.

## Import RIAL

Use Settings, choose a RIAL CSV, run Preview, then Commit if the validation passes. Commit archives the current raw CSV before replacing it.
