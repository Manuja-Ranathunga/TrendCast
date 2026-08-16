# TrendCast

TrendCast tracks YouTube channels and videos for Sri Lankan content creators and
forecasts view-count trajectories for planned uploads.

The repo is split into three parts that share one Supabase/PostgreSQL database:

```
youtube-etl-pipeline/   ETL pipeline: Kafka + Spark + Airflow, collects channel
                         and video stats into Postgres. Runs on schedule via
                         GitHub Actions (.github/workflows/youtube_etl.yml) or
                         locally via Docker Compose.
backend/                FastAPI service that reads from the same database and
                         serves channels, videos, timeseries, and a (currently
                         placeholder) forecast endpoint.
frontend/                Vite + React UI that consumes the backend API: browse
                         channels, inspect real view trajectories, and try the
                         forecast form.
```

## Data flow

```
YouTube Data API v3
        │
        ▼
youtube-etl-pipeline (Kafka → Spark → Airflow)
        │
        ▼
Supabase / PostgreSQL  (channel_stats, videos, view_timeseries, ...)
        │
        ▼
backend (FastAPI)  ──►  frontend (React)
```

All three parts read/write the same database via the `SUPABASE_DB_URL`
connection string — there is no separate database config per component.

## Getting started

Each part has its own setup instructions:

- **ETL pipeline** — see [youtube-etl-pipeline/README.md](youtube-etl-pipeline/README.md)
  for Docker Compose setup, Airflow DAGs, and the database schema.
- **Backend** — from `backend/`, install `requirements.txt`, set `SUPABASE_DB_URL`
  (see `backend/.env.example`), and run `uvicorn main:app --reload`. It serves on
  `http://127.0.0.1:8000` and exposes `/health`, `/channels`,
  `/channels/{channel_id}/videos`, `/videos/{video_id}/timeseries`, and `/forecast`.
- **Frontend** — see [frontend/README.md](frontend/README.md) for install and run
  instructions (`npm install && npm run dev`, served at `http://localhost:5173`).

Database schema and table reference live in [CLAUDE.md](CLAUDE.md).

## Status

The forecasting endpoint currently returns a hardcoded mock curve — the real
predictive model is not yet integrated. Everything else (channel/video/timeseries
data) reflects live data collected by the ETL pipeline.
