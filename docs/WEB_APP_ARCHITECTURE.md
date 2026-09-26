# Analisis Financiero Web MVP

## Scope

This app migrates the Power BI interaction layer to a local web MVP while keeping the existing data pipeline as the source of truth.

## Architecture

- Existing ETL remains in `src/` and reads `raw/` plus `config/`.
- Existing Parquet outputs remain in `output/`.
- The backend reads Parquet with DuckDB and exposes FastAPI endpoints.
- RIAL imports run through the existing ETL in a staging workspace before any commit.
- The frontend is a local Next.js app under `app/frontend`.

## Data Boundaries

The web app does not modify PBIP/PBIR files, Power BI report pages, semantic model relationships, or DAX. Planner overrides only update `config/budget_next_month_overrides.csv` and then rerun the existing ETL.

## Runtime

- Backend: `app/backend`
- Frontend: `app/frontend`
- Operational SQLite metadata: `app/data/app.db`
- Raw archive: `archive/rial`
- Temporary import staging: `app/data/imports`
